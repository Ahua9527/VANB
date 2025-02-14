# core/ndi_manager.py
import logging
from typing import List, Optional, Set
from dataclasses import dataclass
from .scanner import NDIScanner

@dataclass
class NDISource:
    """NDI源信息"""
    name: str
    is_active: bool = True

class NDIManager:
    """NDI管理器，用于管理NDI源的扫描和名称生成"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.scanner = NDIScanner()
        self._known_sources: Set[str] = set()

    def scan_sources(self, timeout_seconds: int = 3) -> List[NDISource]:
        """
        扫描当前网络中的NDI源
        
        Args:
            timeout_seconds: 扫描超时时间（秒）
            
        Returns:
            List[NDISource]: NDI源列表
        """
        # 扫描源
        sources = self.scanner.scan_sources(timeout_seconds)
        if sources is None:
            return []
            
        # 构造返回结果
        result = []
        current_sources = set(sources)
        
        for source in sources:
            result.append(NDISource(
                name=source,
                is_active=True
            ))
            
        return sorted(result, key=lambda x: x.name)

    def _get_sequence_number(self, ndi_names: List[str]) -> int:
        """
        获取新的序列号，保持原有逻辑
        
        Args:
            ndi_names: 当前NDI源名称列表
            
        Returns:
            int: 新的序列号
        """
        existing_numbers = set()
        for name in ndi_names:
            if "VANB-Rx-" in name:
                try:
                    number = int(name.split("VANB-Rx-")[-1].split(")")[0])
                    if number > 0:
                        existing_numbers.add(number)
                except (ValueError, IndexError):
                    continue
        
        sequence_number = 1
        while sequence_number in existing_numbers:
            sequence_number += 1
        
        return sequence_number

    def _verify_ndi_name(self, ndi_name: str, ndi_names: List[str]) -> bool:
        """验证新生成的NDI名称是否有效且不重复"""
        if not ndi_name.startswith("VANB-Rx-"):
            return False
        
        try:
            number = int(ndi_name.split("-")[-1])
            if number <= 0:
                return False
        except ValueError:
            return False
        
        return not any(ndi_name == existing_name for existing_name in ndi_names)

    def generate_unique_name(self, prefix: str = "VANB-Rx") -> str:
        """
        生成唯一的NDI名称，与原有逻辑保持一致
        
        Args:
            prefix: 名称前缀
            
        Returns:
            str: 生成的唯一名称
        """
        # 扫描NDI源
        sources = self.scan_sources()
        ndi_names = [source.name for source in sources]
        
        if not ndi_names:
            self.logger.debug("未扫描到任何NDI源")
        else:
            for name in ndi_names:
                self.logger.info(f"{name}")
        
        # 获取新的序列号
        sequence_number = self._get_sequence_number(ndi_names)
        new_ndi_name = f"{prefix}-{sequence_number}"
        
        # 验证新生成的NDI名称
        if not self._verify_ndi_name(new_ndi_name, ndi_names):
            raise ValueError(f"无法使用NDI名称: {new_ndi_name} (已被占用)")
        
        self.logger.info(f"将使用新的NDI名称: {new_ndi_name}")
        return new_ndi_name