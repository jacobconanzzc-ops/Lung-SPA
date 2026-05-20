"""
NII Model wrapper
"""
from backend.applications.nii.NII_model import NII as NIIModelBase


class NIIModel:
    """NII模型单例封装"""
    _instance = None
    
    @classmethod
    def get_instance(cls, logger=None):
        """获取NII模型实例（单例模式）"""
        if cls._instance is None:
            print("Init NII model")
            cls._instance = NIIModelBase(logger)
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """重置模型实例"""
        cls._instance = None

