"""
视觉验证工具

提供图像比较、差异分析和视觉回归测试功能
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from enum import Enum

# 尝试导入可选依赖
try:
    from skimage.metrics import structural_similarity as ssim
    _SSIM_AVAILABLE = True
except ImportError:
    _SSIM_AVAILABLE = False

from config import settings, PROJECT_ROOT
from logger import logger


class ComparisonAlgorithm(Enum):
    """图像比较算法枚举"""
    MSE = "mse"          # 均方误差
    SSIM = "ssim"        # 结构相似性
    PSNR = "psnr"        # 峰值信噪比
    CUSTOM = "custom"    # 自定义算法（直方图相关性）


class VisualValidator:
    """
    视觉验证工具

    用于比较测试截图与基准图像，检测视觉回归
    """

    def __init__(
        self,
        baseline_dir: Optional[str] = None,
        test_dir: Optional[str] = None,
        diff_dir: Optional[str] = None,           # 修正类型注解
        threshold: Optional[float] = None,
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
        self.threshold = threshold or settings.visual_threshold
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

    def _build_result(
        self,
        success: bool,
        message: str,
        similarity: float,
        threshold: float,
        test_path: Path,
        baseline_path: Path,
        diff_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """构建统一的验证结果字典，减少重复代码"""
        return {
            "success": success,
            "message": message,
            "similarity": similarity,
            "threshold": threshold,
            "test_image": str(test_path),
            "baseline_image": str(baseline_path),
            "diff_image": str(diff_path) if diff_path else None
        }

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
        if not baseline_image_name:
            baseline_image_name = test_image_name
        if threshold is None:
            threshold = self.threshold

        # 使用纯文件名避免路径注入
        safe_test_name = Path(test_image_name).name
        safe_baseline_name = Path(baseline_image_name).name

        test_path = self.test_dir / safe_test_name
        baseline_path = self.baseline_dir / safe_baseline_name
        diff_path = self.diff_dir / f"diff_{safe_test_name}"

        # 检查文件是否存在
        if not test_path.exists():
            logger.error(f"测试图像不存在: {test_path}")
            return self._build_result(False, f"测试图像不存在: {test_path}", 0.0, threshold, test_path, baseline_path)

        if not baseline_path.exists():
            logger.info(f"基准图像不存在: {baseline_path}")  # 降级为 info，避免过多警告
            return self._build_result(False, f"基准图像不存在: {baseline_path}", 0.0, threshold, test_path, baseline_path)

        try:
            test_img = cv2.imread(str(test_path))
            baseline_img = cv2.imread(str(baseline_path))

            if test_img is None:
                logger.error(f"无法读取测试图像: {test_path}")
                return self._build_result(False, f"无法读取测试图像: {test_path}", 0.0, threshold, test_path, baseline_path)

            if baseline_img is None:
                logger.error(f"无法读取基准图像: {baseline_path}")
                return self._build_result(False, f"无法读取基准图像: {baseline_path}", 0.0, threshold, test_path, baseline_path)

            # 确保图像尺寸一致
            if test_img.shape != baseline_img.shape:
                logger.warning(
                    f"{test_image_name} 图像尺寸不一致，调整测试图像尺寸: {test_img.shape} vs {baseline_img.shape}")
                test_img = cv2.resize(test_img, (baseline_img.shape[1], baseline_img.shape[0]))

            # 计算相似度
            similarity = self._calculate_similarity(test_img, baseline_img)
            success = similarity >= threshold

            diff_image_path = None
            if generate_diff:
                diff_image_path = self._generate_diff_image(test_img, baseline_img, diff_path)

            result = self._build_result(
                success,
                f"相似度: {similarity:.4f}, 阈值: {threshold}",
                similarity,
                threshold,
                test_path,
                baseline_path,
                diff_image_path
            )

            logger.info(f"{test_image_name} 视觉验证结果: {'通过' if success else '失败'} - {result['message']}")
            return result

        except Exception as e:
            logger.error(f"视觉验证失败: {e}", exc_info=True)
            return self._build_result(False, f"验证过程发生错误: {str(e)}", 0.0, threshold, test_path, baseline_path)

    def _calculate_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """
        计算两个图像的相似度

        Args:
            img1: 第一个图像
            img2: 第二个图像

        Returns:
            float: 相似度 (0-1)
        """
        if self.algorithm == ComparisonAlgorithm.MSE:
            return self._calculate_mse_similarity(img1, img2)
        elif self.algorithm == ComparisonAlgorithm.SSIM:
            return self._calculate_ssim(img1, img2)
        elif self.algorithm == ComparisonAlgorithm.PSNR:
            return self._calculate_psnr_similarity(img1, img2)
        else:
            return self._calculate_custom(img1, img2)

    @staticmethod
    def _calculate_mse_similarity(img1: np.ndarray, img2: np.ndarray) -> float:
        """基于 MSE 的图像相似度 (0-1)"""
        if img1.shape != img2.shape:
            raise ValueError(f"图像形状不匹配：{img1.shape} vs {img2.shape}")

        data_range = max(img1.max(), img2.max())
        if data_range <= 1.0:
            data_range = 1.0

        mse = np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)
        if mse == 0:
            return 1.0

        similarity = 1 - (mse / (data_range ** 2))
        return float(np.clip(similarity, 0.0, 1.0))

    @staticmethod
    def _calculate_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
        """计算结构相似性 (SSIM) - 使用 scikit-image"""
        if not _SSIM_AVAILABLE:
            logger.error("scikit-image 未安装，无法计算 SSIM。请执行: pip install scikit-image")
            # 降级到 MSE 相似度
            return VisualValidator._calculate_mse_similarity(img1, img2)

        if img1.shape != img2.shape:
            raise ValueError(f"图像形状不匹配：{img1.shape} vs {img2.shape}")

        # 确定数据范围
        data_range = max(img1.max(), img2.max()) - min(img1.min(), img2.min())
        if data_range == 0:
            data_range = 255.0

        # 如果是彩色图像且 scikit-image 版本支持，直接使用 channel_axis
        if len(img1.shape) == 3 and img1.shape[2] == 3:
            # 新版 scikit-image 使用 channel_axis，旧版用 multichannel
            try:
                score = ssim(img1, img2, channel_axis=2, data_range=data_range)
            except TypeError:
                score = ssim(img1, img2, multichannel=True, data_range=data_range)
        else:
            # 灰度图或四通道以上转为灰度
            if len(img1.shape) == 3:
                gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            else:
                gray1, gray2 = img1, img2
            score = ssim(gray1, gray2, data_range=data_range)

        return float(score)

    @staticmethod
    def _calculate_psnr_similarity(img1: np.ndarray, img2: np.ndarray, psnr_max: float = 50.0) -> float:
        """
        计算基于 PSNR 的图像相似度 (0-1)
        采用线性映射并钳位，更符合直观预期
        """
        if img1.shape != img2.shape:
            raise ValueError(f"图像形状不匹配：{img1.shape} vs {img2.shape}")

        data_range = max(img1.max(), img2.max()) - min(img1.min(), img2.min())
        if data_range <= 0:
            data_range = 255.0
        elif data_range <= 1.0:
            data_range = 1.0

        mse = np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)
        if mse == 0:
            return 1.0

        psnr = 20 * np.log10(data_range / np.sqrt(mse))
        # 线性映射：PSNR 超过 psnr_max 视为完全相似，低于 0 视为完全不相似
        similarity = psnr / psnr_max
        return float(np.clip(similarity, 0.0, 1.0))

    @staticmethod
    def _calculate_custom(img1: np.ndarray, img2: np.ndarray) -> float:
        """
        基于直方图相关性的图像相似度 (0-1)
        注意：仅比较颜色分布，忽略空间结构
        """
        # 转换为灰度（处理多通道情况）
        def to_gray(img: np.ndarray) -> np.ndarray:
            if len(img.shape) == 3:
                if img.shape[2] == 4:  # RGBA
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
                else:  # BGR
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return img.astype(np.uint8)

        gray1 = to_gray(img1)
        gray2 = to_gray(img2)

        hist1 = cv2.calcHist([gray1], [0], None, [256], [0, 256])
        hist2 = cv2.calcHist([gray2], [0], None, [256], [0, 256])

        hist1 = cv2.normalize(hist1, hist1).flatten()
        hist2 = cv2.normalize(hist2, hist2).flatten()

        correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        similarity = (correlation + 1) / 2.0
        return float(np.clip(similarity, 0.0, 1.0))

    @staticmethod
    def _generate_diff_image(img1: np.ndarray, img2: np.ndarray, output_path: Path) -> Optional[Path]:
        """
        生成差异图像，兼容灰度图

        Args:
            img1: 第一个图像
            img2: 第二个图像
            output_path: 输出路径

        Returns:
            Path: 差异图像路径，失败返回 None
        """
        try:
            diff = cv2.absdiff(img1, img2)

            # 处理灰度图
            if len(diff.shape) == 3:
                gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            else:
                gray = diff

            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 确保 result 与 img1 类型一致
            if len(img1.shape) == 3:
                result = img1.copy()
                cv2.drawContours(result, contours, -1, (0, 0, 255), 2)
                mask = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                mask[:, :, 1] = 0
                mask[:, :, 2] = 0
                result = cv2.addWeighted(result, 0.7, mask, 0.3, 0)
            else:
                # 灰度图直接转为三通道显示
                result = cv2.cvtColor(img1, cv2.COLOR_GRAY2BGR)
                cv2.drawContours(result, contours, -1, (0, 0, 255), 2)
                mask = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                mask[:, :, 1] = 0
                mask[:, :, 2] = 0
                result = cv2.addWeighted(result, 0.7, mask, 0.3, 0)

            cv2.imwrite(str(output_path), result)
            logger.debug(f"差异图像已生成: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"生成差异图像失败: {e}")
            return None

    def update_baseline(self, test_image_name: str, baseline_image_name: Optional[str] = None) -> bool:
        """将测试图像更新为基准图像"""
        if not baseline_image_name:
            baseline_image_name = test_image_name

        safe_test_name = Path(test_image_name).name
        safe_baseline_name = Path(baseline_image_name).name

        test_path = self.test_dir / safe_test_name
        baseline_path = self.baseline_dir / safe_baseline_name

        if not test_path.exists():
            logger.error(f"测试图像不存在: {test_path}")
            return False

        try:
            import shutil
            shutil.copy2(str(test_path), str(baseline_path))
            logger.info(f"基准图像已更新: {baseline_path}")
            return True
        except Exception as e:
            logger.error(f"更新基准图像失败: {e}", exc_info=True)
            return False

    def validate_directory(self, threshold: Optional[float] = None) -> Dict[str, Any]:
        """验证整个目录中的图像"""
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
            "pass_rate": passed * 100 / len(test_images) if test_images else 0.0,
            "results": results
        }

        logger.info(
            f"目录验证完成: 总计 {len(test_images)}, 通过 {passed}, 失败 {failed}, 通过率 {summary['pass_rate']:.2f}%")
        return summary

    def get_baseline_images(self) -> List[str]:
        """获取所有基准图像文件名"""
        return [f.name for f in self.baseline_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]

    def get_test_images(self) -> List[str]:
        """获取所有测试图像文件名"""
        return [f.name for f in self.test_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg')]


# 便捷函数
def validate_screenshot(
    screenshot_path: str,
    baseline_path: Optional[str] = None,
    threshold: float = 0.92
) -> Dict[str, Any]:
    """便捷函数：验证单个截图"""
    validator = VisualValidator()
    screenshot_name = Path(screenshot_path).name
    baseline_name = Path(baseline_path).name if baseline_path else None
    return validator.validate(screenshot_name, baseline_name, threshold)


def update_baseline(
    screenshot_path: str,
    baseline_path: Optional[str] = None
) -> bool:
    """便捷函数：更新基准图像"""
    validator = VisualValidator()
    screenshot_name = Path(screenshot_path).name
    baseline_name = Path(baseline_path).name if baseline_path else None
    return validator.update_baseline(screenshot_name, baseline_name)


if __name__ == "__main__":
    # 示例用法（需要配置文件和目录存在）
    print("视觉验证工具模块已加载。请在测试框架中调用。")