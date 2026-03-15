"""
XGBoost模型实现 - 梯度提升树预测

功能：
- 滚动窗口训练
- 时序交叉验证
- 特征重要性分析
"""

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, mean_squared_error, mean_absolute_error

# XGBoost导入
import xgboost as xgb

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class XGBoostConfig:
    """XGBoost模型配置"""
    # 模型参数
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    colsample_bylevel: float = 0.8
    min_child_weight: int = 1
    gamma: float = 0
    reg_alpha: float = 0.1  # L1正则化
    reg_lambda: float = 1.0  # L2正则化
    scale_pos_weight: float = 1.0

    # 训练参数
    early_stopping_rounds: int = 20
    eval_metric: str = 'rmse'  # 或 'logloss', 'auc', 'mae'

    # 任务类型
    objective: str = 'reg:squarederror'  # 或 'binary:logistic', 'multi:softprob'
    num_class: int = 1  # 分类任务的类别数

    # 时序参数
    prediction_horizon: int = 1


def get_xgb_params(config: XGBoostConfig) -> Dict[str, Any]:
    """从配置生成XGBoost参数"""
    params = {
        'n_estimators': config.n_estimators,
        'max_depth': config.max_depth,
        'learning_rate': config.learning_rate,
        'subsample': config.subsample,
        'colsample_bytree': config.colsample_bytree,
        'colsample_bylevel': config.colsample_bylevel,
        'min_child_weight': config.min_child_weight,
        'gamma': config.gamma,
        'reg_alpha': config.reg_alpha,
        'reg_lambda': config.reg_lambda,
        'scale_pos_weight': config.scale_pos_weight,
        'objective': config.objective,
        'random_state': 42,
        'n_jobs': -1,
        'early_stopping_rounds': config.early_stopping_rounds,
    }

    if config.num_class > 1:
        params['num_class'] = config.num_class

    return params


class XGBoostModel:
    """XGBoost预测模型"""

    def __init__(self, config: Optional[XGBoostConfig] = None, model_path: Optional[str] = None):
        self.config = config or XGBoostConfig()
        self.model: Optional[xgb.XGBModel] = None
        self.feature_names: List[str] = []
        self.feature_importance: Optional[pd.DataFrame] = None

        if model_path and Path(model_path).exists():
            self.load(model_path)

    def _get_model(self) -> xgb.XGBModel:
        """根据配置创建模型实例"""
        params = get_xgb_params(self.config)

        if self.config.objective.startswith('reg'):
            model = xgb.XGBRegressor(**params)
        elif self.config.objective.startswith('multi'):
            model = xgb.XGBClassifier(**params)
        else:
            model = xgb.XGBClassifier(**params)

        return model

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        verbose: bool = True
    ) -> Dict:
        """
        训练模型

        Args:
            X_train: 训练特征
            y_train: 训练目标
            X_val: 验证特征
            y_val: 验证目标
            verbose: 是否输出日志

        Returns:
            训练信息
        """
        self.feature_names = X_train.columns.tolist()

        # 创建模型
        self.model = self._get_model()

        # 准备验证集
        eval_set = [(X_train, y_train)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))

        # 训练
        logger.info(f"开始XGBoost训练: {len(X_train)}样本, {len(self.feature_names)}特征")

        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            verbose=verbose
        )

        # 记录最佳迭代次数
        best_iteration = self.model.best_iteration if hasattr(self.model, 'best_iteration') else self.config.n_estimators
        logger.info(f"训练完成. Best iteration: {best_iteration}")

        # 计算特征重要性
        self._calculate_feature_importance()

        # 评估
        train_pred = self.model.predict(X_train)
        train_metrics = self._calculate_metrics(y_train, train_pred)

        results = {
            'best_iteration': best_iteration,
            'train_metrics': train_metrics
        }

        if X_val is not None:
            val_pred = self.model.predict(X_val)
            val_metrics = self._calculate_metrics(y_val, val_pred)
            results['val_metrics'] = val_metrics

        return results

    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """计算评估指标"""
        metrics = {}

        # 基础指标
        metrics['mse'] = mean_squared_error(y_true, y_pred)
        metrics['rmse'] = np.sqrt(metrics['mse'])
        metrics['mae'] = mean_absolute_error(y_true, y_pred)

        # 方向准确率
        if len(y_true) > 1 and y_true.dtype != object:
            true_direction = np.sign(y_true)
            pred_direction = np.sign(y_pred)
            metrics['direction_accuracy'] = np.mean(true_direction == pred_direction)

        return metrics

    def predict(self, X: pd.DataFrame, return_proba: bool = False) -> np.ndarray:
        """
        预测

        Args:
            X: 特征DataFrame
            return_proba: 是否返回概率 (分类任务)

        Returns:
            预测结果
        """
        if self.model is None:
            raise ValueError("模型未训练")

        if return_proba and hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba(X)

        return self.model.predict(X)

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """
        评估模型

        Returns:
            评估指标
        """
        predictions = self.predict(X_test)

        metrics = self._calculate_metrics(y_test.values, predictions)

        # 分类任务额外指标
        if self.config.objective != 'reg:squarederror' or len(np.unique(y_test)) <= 5:
            pred_classes = np.round(predictions).astype(int)
            metrics['accuracy'] = accuracy_score(y_test, pred_classes)

        return metrics

    def _calculate_feature_importance(self) -> pd.DataFrame:
        """计算特征重要性"""
        if self.model is None:
            return pd.DataFrame()

        importance = self.model.feature_importances_

        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)

        self.feature_importance = importance_df

        return importance_df

    def get_top_features(self, n: int = 10) -> pd.DataFrame:
        """获取最重要的特征"""
        if self.feature_importance is None:
            self._calculate_feature_importance()

        return self.feature_importance.head(n)

    def time_series_cv(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_splits: int = 5,
        test_size: Optional[int] = None
    ) -> Dict[str, List[float]]:
        """
        时序交叉验证

        Args:
            X: 特征
            y: 目标
            n_splits: 折数
            test_size: 每折测试集大小

        Returns:
            各折评估指标
        """
        results = {
            'rmse': [],
            'mae': [],
            'direction_accuracy': []
        }

        # 时序分割
        if test_size is None:
            test_size = len(X) // (n_splits + 1)

        tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)

        for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
            logger.info(f"交叉验证 Fold {fold + 1}/{n_splits}")

            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            # 训练新模型
            self.model = None
            self.fit(X_train, y_train, verbose=False)

            # 评估
            fold_metrics = self.evaluate(X_test, y_test)

            for key in results:
                if key in fold_metrics:
                    results[key].append(fold_metrics[key])

        # 计算平均值
        summary = {f'{k}_mean': np.mean(v) for k, v in results.items()}
        summary.update({f'{k}_std': np.std(v) for k, v in results.items()})

        return {**results, **summary}

    def rolling_window_train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        window_size: int = 252 * 3,
        step_size: int = 63,
        min_train_size: int = 252
    ) -> List[Dict]:
        """
        滚动窗口训练

        Returns:
            各窗口结果列表
        """
        results = []
        n = len(X)

        start_idx = min_train_size

        while start_idx + window_size < n:
            train_end = start_idx
            test_end = min(start_idx + window_size, n)

            window_date = X.index[start_idx]
            logger.info(f"滚动窗口训练: {window_date}")

            X_train = X.iloc[start_idx - min_train_size:start_idx]
            y_train = y.iloc[start_idx - min_train_size:start_idx]
            X_test = X.iloc[start_idx:test_end]
            y_test = y.iloc[start_idx:test_end]

            # 训练
            self.model = None
            self.fit(X_train, y_train, verbose=False)

            # 评估
            metrics = self.evaluate(X_test, y_test)
            metrics['window_date'] = str(window_date)
            metrics['train_size'] = len(X_train)
            metrics['test_size'] = len(X_test)

            # 保存特征重要性
            top_features = self.get_top_features(5)
            metrics['top_features'] = top_features['feature'].tolist()

            results.append(metrics)

            start_idx += step_size

        return results

    def save(self, path: str) -> None:
        """保存模型"""
        if self.model is None:
            raise ValueError("模型未训练")

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # XGBoost原生保存
        self.model.save_model(path)

        # 保存配置和特征名
        import json
        config_path = Path(path).with_suffix('.config.json')
        with open(config_path, 'w') as f:
            json.dump({
                'feature_names': self.feature_names,
                'config': self.config.__dict__
            }, f)

        logger.info(f"模型已保存到: {path}")

    def load(self, path: str) -> None:
        """加载模型"""
        # 先加载配置，以便创建正确类型的模型
        import json
        config_path = Path(path).with_suffix('.config.json')
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = json.load(f)
                self.feature_names = data['feature_names']
                # 恢复配置
                for key, value in data['config'].items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)

        # 根据配置创建正确类型的模型，然后加载权重
        self.model = self._get_model()
        self.model.load_model(path)

        logger.info(f"模型已从{path}加载")
