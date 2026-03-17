"""
视觉验证工具

提供图像比较、差异分析和视觉回归测试功能
"""
import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum

from config import settings, PROJECT_ROOT
from utils.logger import logger



class ComparisonAlgorithm(Enum):
    """图像比较算法枚举"""
    MSE = "mse"  # 均方误差
    SSIM = "ssim"  # 结构相似性
    PSNR = "psnr"  # 峰值信噪比
    CUSTOM = "custom"  # 自定义算法


class VisualValidator:
    """
    视觉验证工具

    用于比较测试截图与基准图像，检测视觉回归
    """

    def __init__(
            self,
            baseline_dir: Optional[str] = None,
            test_dir: Optional[str] = None,
            diff_dir: Optional[str] = None,
            threshold: float = 0.92,
            algorithm: ComparisonAlgorithm = ComparisonAlgorithm.SSIM
    ):
        """
        初始化视觉验证工具

        Args:
            baseline_dir: 基准图像目录
            test_dir: 测试图像目录
            diff_dir: 差异图像输出目录
            threshold: 相似度阈值 (0-1), 大于此值视为通过
            algorithm: 图像比较算法
        """
        # 从配置读取默认值
        self.baseline_dir = Path(baseline_dir or PROJECT_ROOT / settings.visual_baseline_dir)
        self.test_dir = Path(test_dir or PROJECT_ROOT / settings.screenshot_dir)
        self.diff_dir = Path(diff_dir or PROJECT_ROOT / settings.visual_diff_dir)
        self.threshold = float(settings.visual_threshold)
        self.algorithm = algorithm

        # 确保目录存在
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.diff_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"VisualValidator initialized with:\n"
                   f"  Baseline dir: {self.baseline_dir}\n"
                   f"  Test dir: {self.test_dir}\n"
                   f"  Diff dir: {self.diff_dir}\n"
                   f"  Threshold: {self.threshold}\n"
                   f"  Algorithm: {self.algorithm.value}")

    def validate(
            self,
            test_image_name: str,
            baseline_image_name: Optional[str] = None,
            threshold: Optional[float] = None,
            generate_diff: bool = True
    ) -> Dict[str, Any]:
        """
        验证测试图像与基准图像的相似度

        Args:
            test_image_name: 测试图像文件名
            baseline_image_name: 基准图像文件名（默认与测试图像相同）
            threshold: 相似度阈值（默认使用初始化时的阈值）
            generate_diff: 是否生成差异图像

        Returns:
            Dict[str, Any]: 验证结果，包含相似度、是否通过、差异图像路径等
        """
       
            
        # 使用默认值
        if not baseline_image_name:
            baseline_image_name = test_image_name
        
        if threshold is None:
            threshold = self.threshold

        # 构建文件路径
        test_path = self.test_dir / test_image_name
        baseline_path = self.baseline_dir / baseline_image_name
        diff_path = self.diff_dir / f"diff_{test_image_name}"

        # 检查文件是否存在
        if not test_path.exists():
            logger.error(f"测试图像不存在: {test_path}")
            return {
                "success": False,
                "message": f"测试图像不存在: {test_path}",
                "similarity": 0.0,
                "threshold": threshold,
                "test_image": str(test_path),
                "baseline_image": str(baseline_path),
                "diff_image": None
            }

        if not baseline_path.exists():
            logger.warning(f"基准图像不存在: {baseline_path}")
            return {
                "success": False,
                "message": f"基准图像不存在: {baseline_path}",
                "similarity": 0.0,
                "threshold": threshold,
                "test_image": str(test_path),
                "baseline_image": str(baseline_path),
                "diff_image": None
            }

        try:
            # 读取图像
            test_img = cv2.imread(str(test_path))
            baseline_img = cv2.imread(str(baseline_path))

            if test_img is None:
                logger.error(f"无法读取测试图像: {test_path}")
                return {
                    "success": False,
                    "message": f"无法读取测试图像: {test_path}",
                    "similarity": 0.0,
                    "threshold": threshold,
                    "test_image": str(test_path),
                    "baseline_image": str(baseline_path),
                    "diff_image": None
                }

            if baseline_img is None:
                logger.error(f"无法读取基准图像: {baseline_path}")
                return {
                    "success": False,
                    "message": f"无法读取基准图像: {baseline_path}",
                    "similarity": 0.0,
                    "threshold": threshold,
                    "test_image": str(test_path),
                    "baseline_image": str(baseline_path),
                    "diff_image": None
                }

            # 确保图像尺寸一致
            if test_img.shape != baseline_img.shape:
                logger.warning(f"图像尺寸不一致，调整测试图像尺寸: {test_img.shape} vs {baseline_img.shape}")
                test_img = cv2.resize(test_img, (baseline_img.shape[1], baseline_img.shape[0]))

            # 计算相似度
            similarity = self._calculate_similarity(test_img, baseline_img)
            success = similarity >= threshold

            # 生成差异图像
            diff_image_path = None
            if generate_diff:
                diff_image_path = self._generate_diff_image(test_img, baseline_img, diff_path)

            result = {
                "success": success,
                "message": f"相似度: {similarity:.4f}, 阈值: {threshold}",
                "similarity": similarity,
                "threshold": threshold,
                "test_image": str(test_path),
                "baseline_image": str(baseline_path),
                "diff_image": str(diff_image_path) if diff_image_path else None
            }

            logger.info(f"视觉验证结果: {'通过' if success else '失败'} - {result['message']}")
            return result

        except Exception as e:
            logger.error(f"视觉验证失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"验证过程发生错误: {str(e)}",
                "similarity": 0.0,
                "threshold": threshold,
                "test_image": str(test_path),
                "baseline_image": str(baseline_path),
                "diff_image": None
            }

    def _calculate_similarity(self, img1, img2) -> float:
        """
        计算两个图像的相似度

        Args:
            img1: 第一个图像
            img2: 第二个图像

        Returns:
            float: 相似度 (0-1)
        """
        if self.algorithm == ComparisonAlgorithm.MSE:
            return self._calculate_mse(img1, img2)
        elif self.algorithm == ComparisonAlgorithm.SSIM:
            return self._calculate_ssim(img1, img2)
        elif self.algorithm == ComparisonAlgorithm.PSNR:
            return self._calculate_psnr(img1, img2)
        else:
            return self._calculate_custom(img1, img2)
    @staticmethod
    def _calculate_mse(img1: np.ndarray, img2: np.ndarray) -> float:
        """
        计算基于 MSE 的图像相似度 (0-1)
        
        Args:
            img1: 第一个图像 (numpy array)
            img2: 第二个图像 (numpy array)

        Returns:
            float: 相似度 (0.0 - 1.0)，1.0 表示完全相同
        """
        # 1. 形状校验
        if img1.shape != img2.shape:
            raise ValueError(f"图像形状不匹配：{img1.shape} vs {img2.shape}")
        
        # 2. 确定像素最大值 (动态适配 0-1 或 0-255)
        # 注意：这里假设两张图的范围一致。通常 uint8 为 255，float 为 1.0
        data_range = np.max([img1.max(), img2.max()])
        if data_range <= 1.0:
            data_range = 1.0
        # 如果不确定，也可以强制传入 data_range 参数，或者默认按 255 处理并转换类型
        
        # 3. 计算 MSE (使用 float64 防止精度损失)
        mse = np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)
        
        # 4. 处理完全相同的情况
        if mse == 0:
            return 1.0
        
        # 5. 计算相似度并钳制 (Clamp) 到 [0, 1] 范围
        similarity = 1 - (mse / (data_range ** 2))
        return float(np.clip(similarity, 0.0, 1.0))

    @staticmethod
    def _calculate_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
        """
        计算结构相似性 (SSIM) - 使用 scikit-image (推荐)
        """
        if img1.shape != img2.shape:
            raise ValueError(f"图像形状不匹配：{img1.shape} vs {img2.shape}")

        # 如果是彩色图像，skimage 的 ssim 默认支持 multichannel，
        # 但通常转为灰度计算更符合传统 SSIM 定义，或者设置 multichannel=True
        # 这里为了兼容原逻辑，如果是 3 通道则转为灰度
        if len(img1.shape) == 3:
            # 注意：skimage 默认是 RGB，OpenCV 是 BGR，但转灰度结果一样
            img1 = np.mean(img1, axis=2).astype(np.float32) 
            img2 = np.mean(img2, axis=2).astype(np.float32)

        # data_range 自动根据 dtype 判断 (255 for uint8, 1.0 for float)
        score = ssim(img1, img2, data_range=img1.max() - img1.min())
        
        return float(score)

    @staticmethod
    def _calculate_psnr_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
        """
        计算基于 PSNR 的图像相似度 - 使用 scikit-image (推荐)
        """
        from skimage.metrics import peak_signal_noise_ratio as psnr
        if img1.shape != img2.shape:
            raise ValueError(f"图像形状不匹配：{img1.shape} vs {img2.shape}")
        
        # 动态确定数据范围
        data_range = img1.max() - img1.min()
        
        # 计算 PSNR
        psnr_value = psnr(img1, img2, data_range=data_range)
        
        # 将 PSNR 映射到 0-1
        # 通常 PSNR > 40dB 认为质量极好，< 20dB 认为质量很差
        # 使用 sigmoid 映射更平滑
        similarity = 1 / (1 + np.exp(-(psnr_value - 30) / 5))
        
        return float(np.clip(similarity, 0.0, 1.0))

    def _calculate_custom(self, img1, img2) -> float:
        """
        自定义相似度计算

        Args:
            img1: 第一个图像
            img2: 第二个图像

        Returns:
            float: 相似度 (0-1)
        """
        # 转换为灰度图像
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        # 计算直方图
        hist1 = cv2.calcHist([gray1], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([gray2], [0], None, [256], [0, 256])

        # 归一化直方图
        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()

        # 计算相关性
        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        return correlation

    def _generate_diff_image(self, img1, img2, output_path: Path) -> str:
        """
        生成差异图像

        Args:
            img1: 第一个图像
            img2: 第二个图像
            output_path: 输出路径

        Returns:
            str: 差异图像路径
        """
        try:
            # 计算差异
            diff = cv2.absdiff(img1, img2)
            
            # 转换为灰度图像
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            
            # 阈值处理
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
            
            # 找到轮廓
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # 在原始图像上绘制轮廓
            result = img1.copy()
            cv2.drawContours(result, contours, -1, (0, 0, 255), 2)
            
            # 添加差异掩码
            mask = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            mask[:, :, 1] = 0  # 绿色通道设为0
            mask[:, :, 2] = 0  # 蓝色通道设为0
            result = cv2.addWeighted(result, 0.7, mask, 0.3, 0)
            
            # 保存差异图像
            cv2.imwrite(str(output_path), result)
            logger.debug(f"差异图像已生成: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.error(f"生成差异图像失败: {e}")
            return None

    def update_baseline(self, test_image_name: str, baseline_image_name: Optional[str] = None) -> bool:
        """
        将测试图像更新为基准图像

        Args:
            test_image_name: 测试图像文件名
            baseline_image_name: 基准图像文件名（默认与测试图像相同）

        Returns:
            bool: 是否更新成功
        """
        if not baseline_image_name:
            baseline_image_name = test_image_name

        test_path = self.test_dir / test_image_name
        baseline_path = self.baseline_dir / baseline_image_name

        if not test_path.exists():
            logger.error(f"测试图像不存在: {test_path}")
            return False

        try:
            # 复制文件
            import shutil
            shutil.copy2(str(test_path), str(baseline_path))
            logger.info(f"基准图像已更新: {baseline_path}")
            return True
        except Exception as e:
            logger.error(f"更新基准图像失败: {e}", exc_info=True)
            return False

    def validate_directory(self, threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        验证整个目录中的图像

        Args:
            threshold: 相似度阈值

        Returns:
            Dict[str, Any]: 目录验证结果
        """
        test_images = [f for f in self.test_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]
        results = []
        passed = 0
        failed = 0

        for test_image in test_images:
            result = self.validate(test_image.name, threshold=threshold)
            results.append(result)
            if result['success']:
                passed += 1
            else:
                failed += 1

        summary = {
            "total": len(test_images),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(test_images) if test_images else 0.0,
            "results": results
        }

        logger.info(f"目录验证完成: 总计 {len(test_images)}, 通过 {passed}, 失败 {failed}, 通过率 {summary['pass_rate']:.2f}")
        return summary

    def get_baseline_images(self) -> List[str]:
        """
        获取所有基准图像文件名

        Returns:
            List[str]: 基准图像文件名列表
        """
        return [f.name for f in self.baseline_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]

    def get_test_images(self) -> List[str]:
        """
        获取所有测试图像文件名

        Returns:
            List[str]: 测试图像文件名列表
        """
        return [f.name for f in self.test_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]


# 便捷函数
def validate_screenshot(
        screenshot_path: str,
        baseline_path: Optional[str] = None,
        threshold: float = 0.92
) -> Dict[str, Any]:
    """
    便捷函数：验证单个截图

    Args:
        screenshot_path: 截图路径
        baseline_path: 基准图像路径
        threshold: 相似度阈值

    Returns:
        Dict[str, Any]: 验证结果
    """
    validator = VisualValidator()
    
    # 提取文件名
    screenshot_name = Path(screenshot_path).name
    baseline_name = Path(baseline_path).name if baseline_path else None
    
    # 验证
    return validator.validate(screenshot_name, baseline_name, threshold)


def update_baseline(
        screenshot_path: str,
        baseline_path: Optional[str] = None
) -> bool:
    """
    便捷函数：更新基准图像

    Args:
        screenshot_path: 截图路径
        baseline_path: 基准图像路径

    Returns:
        bool: 是否更新成功
    """
    validator = VisualValidator()
    
    # 提取文件名
    screenshot_name = Path(screenshot_path).name
    baseline_name = Path(baseline_path).name if baseline_path else None
    
    # 更新
    return validator.update_baseline(screenshot_name, baseline_name)


if __name__ == "__main__":
    """示例用法"""
    validator = VisualValidator()
    
    # 验证单个图像
    result = validator.validate("quick_shot.png")
    print(f"验证结果: {result}")
    
    # 验证整个目录
    directory_result = validator.validate_directory()
    print(f"目录验证结果: {directory_result}")
    
    # 更新基准图像
    # validator.update_baseline("test_viewport.png")
