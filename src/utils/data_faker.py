import json
import csv
import random
import string
from datetime import datetime, timezone
from typing import (
    Any, Callable, Dict, List, Optional, Union, Protocol, runtime_checkable
)
from dataclasses import dataclass
from pathlib import Path
import asyncio
from tqdm import tqdm as sync_tqdm
from tqdm.asyncio import tqdm as async_tqdm
from faker import Faker

from config import settings
from utils.logger import logger


# ==================== 生成策略协议 ====================
@runtime_checkable
class GeneratorStrategy(Protocol):
    """生成策略协议 - 支持自定义生成逻辑"""

    def generate(self, context: Optional[Dict[str, Any]] = None) -> Any:
        ...


# ==================== 核心生成器 ====================
class TestDataGenerator:
    """高性能测试数据生成器 - 基于 Faker 构建"""

    def __init__(self, locale: str = 'zh_CN'):
        self.faker: Faker = Faker(locale)
        self._strategies: Dict[str, GeneratorStrategy] = {}
        logger.info("TestDataGenerator initialized")

    # ---------- 基础类型生成 ----------
    @staticmethod
    def random_string(
            length: int = 10,
            chars: str = string.ascii_letters + string.digits
    ) -> str:
        """生成随机字符串（原生实现）"""
        return ''.join(random.choices(chars, k=length))

    @staticmethod
    def random_int( min_val: int = 0, max_val: int = 100) -> int:
        """生成随机整数"""
        return random.randint(min_val, max_val)
    @staticmethod
    def random_float( min_val: float = 0.0, max_val: float = 100.0, decimals: int = 2) -> float:
        """生成随机浮点数"""
        return round(random.uniform(min_val, max_val), decimals)

    @staticmethod
    def random_bool( true_prob: float = 0.5) -> bool:
        """生成随机布尔值"""
        return random.random() < true_prob

    @staticmethod
    def random_choice( choices: List[Any], weights: Optional[List[float]] = None) -> Any:
        """从列表中随机选择"""
        if weights:
            return random.choices(choices, weights=weights, k=1)[0]
        return random.choice(choices)

    # ---------- Faker 增强的业务数据生成 ----------
    def generate_username(self) -> str:
        """生成用户名"""
        return self.faker.user_name()

    def generate_email(self, domain: Optional[str] = None) -> str:
        """生成邮箱地址"""
        if domain:
            username = self.faker.user_name()
            return f"{username}@{domain}"
        return self.faker.email()

    def generate_phone(self) -> str:
        """生成手机号码（根据 locale 自动适配）"""
        return self.faker.phone_number()

    def generate_address(self) -> str:
        """生成地址（自动处理多行 -> 单行）"""
        return self.faker.address().replace('\n', ' ')

    def generate_company(self) -> str:
        """生成公司名称"""
        return self.faker.company()

    def generate_job(self) -> str:
        """生成职位"""
        return self.faker.job()

    def generate_credit_card(self) -> Dict[str, str]:
        """生成信用卡信息（测试用）"""
        return {
            "number": self.faker.credit_card_number(),
            "provider": self.faker.credit_card_provider(),
            "expire": self.faker.credit_card_expire(),
            "cvv": self.faker.credit_card_security_code()
        }

    def generate_ipv4(self) -> str:
        """生成 IPv4 地址"""
        return self.faker.ipv4()

    def generate_mac_address(self) -> str:
        """生成 MAC 地址"""
        return self.faker.mac_address()

    def generate_url(self) -> str:
        """生成 URL"""
        return self.faker.url()

    def generate_text(self, max_nb_chars: int = 200) -> str:
        """生成随机文本"""
        return self.faker.text(max_nb_chars=max_nb_chars)

    def generate_sentence(self, nb_words: int = 6) -> str:
        """生成句子"""
        return self.faker.sentence(nb_words=nb_words)

    def generate_paragraph(self, nb_sentences: int = 3) -> str:
        """生成段落"""
        return self.faker.paragraph(nb_sentences=nb_sentences)

    def generate_date_time(
            self,
            start_date: str = "-30y",
            end_date: str = "now",
            tzinfo: Optional[timezone] = None
    ) -> datetime:
        """生成随机 datetime"""
        return self.faker.date_time_between(start_date=start_date, end_date=end_date, tzinfo=tzinfo)

    def generate_date(self, pattern: str = "%Y-%m-%d") -> str:
        """生成格式化日期字符串"""
        return self.faker.date(pattern=pattern)

    def generate_time(self, pattern: str = "%H:%M:%S") -> str:
        """生成格式化时间字符串"""
        return self.faker.time(pattern=pattern)

    def generate_uuid(self, short: bool = False, upper: bool = True) -> str:
        """
        生成 UUID（修复原始错误的核心方法）

        :param short: 是否返回短格式（8位十六进制）
        :param upper: 是否大写
        :return: UUID 字符串
        """
        uuid_str = self.faker.uuid4()
        if short:
            # 移除连字符后取前8位
            cleaned = uuid_str.replace('-', '')
            result = cleaned[:8]
            return result.upper() if upper else result.lower()
        return uuid_str.upper() if upper else uuid_str.lower()

    # ---------- 复杂结构生成 ----------
    @staticmethod
    def generate_dict(
            schema: Dict[str, Callable[[], Any]],
            count: int = 1
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """根据 schema 生成字典结构"""

        def _gen_one():
            return {key: gen() for key, gen in schema.items()}

        if count == 1:
            return _gen_one()
        return [_gen_one() for _ in range(count)]

    def generate_list(
            self,
            item_generator: Callable[[], Any],
            min_len: int = 1,
            max_len: int = 10
    ) -> List[Any]:
        """生成随机长度的列表"""
        length = self.random_int(min_len, max_len)
        return [item_generator() for _ in range(length)]

    # ---------- 批量生成（同步）----------
    @staticmethod
    def batch_generate(
            schema: Dict[str, Callable[[], Any]],
            count: int = 100,
            show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """批量生成结构化数据（同步）"""
        logger.info(f"Starting batch generation of {count} records")

        results = []
        iterable = range(count)
        if show_progress:
            iterable = sync_tqdm(iterable, desc="Generating test data", unit="record")

        for _ in iterable:
            record = {key: gen() for key, gen in schema.items()}
            results.append(record)

        logger.info(f"Successfully generated {len(results)} records")
        return results

    # ---------- 异步批量生成 ----------
    @staticmethod
    async def batch_generate_async(
            schema: Dict[str, Callable[[], Any]],
            count: int = 100,
            concurrency: int = 10,
            show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """异步批量生成数据，支持并发控制"""
        logger.info(f"Starting async batch generation of {count} records (concurrency={concurrency})")

        semaphore = asyncio.Semaphore(concurrency)

        async def _generate_one() -> Dict[str, Any]:
            async with semaphore:
                # 让出控制权以支持并发调度
                await asyncio.sleep(0)
                return {key: gen() for key, gen in schema.items()}

        tasks = [_generate_one() for _ in range(count)]

        if show_progress:
            results = []
            for coro in async_tqdm.as_completed(tasks, desc="Generating async data", unit="record"):
                results.append(await coro)
        else:
            results = await asyncio.gather(*tasks)

        logger.info(f"Successfully generated {len(results)} records asynchronously")
        return results

    # ---------- 自定义策略注册 ----------
    def register_strategy(self, name: str, strategy: GeneratorStrategy) -> None:
        """注册自定义生成策略"""
        self._strategies[name] = strategy
        logger.debug(f"Registered custom strategy: {name}")

    def use_strategy(self, name: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """使用已注册的策略生成数据"""
        if name not in self._strategies:
            raise ValueError(f"Strategy '{name}' not registered")
        return self._strategies[name].generate(context)

    # ---------- 数据导出 ----------
    @staticmethod
    def export_to_json(
            data: Union[Dict, List],
            filepath: Path,
            indent: int = 2,
            ensure_ascii: bool = False
    ) -> None:
        """导出为 JSON 文件"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

        record_count = len(data) if isinstance(data, list) else 1
        logger.info(f"Exported {record_count} record(s) to JSON: {filepath}")

    @staticmethod
    def export_to_csv(
            data: List[Dict],
            filepath: Path,
            fieldnames: Optional[List[str]] = None
    ) -> None:
        """导出为 CSV 文件（utf-8-sig 兼容 Excel）"""
        if not data:
            raise ValueError("No data to export")

        if fieldnames is None:
            fieldnames = list(data[0].keys())

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        logger.info(f"Exported {len(data)} records to CSV: {filepath}")


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 初始化生成器（带种子保证可重复性）
    generator = TestDataGenerator()

    # 示例1：生成用户数据 schema（充分利用 Faker）
    user_schema = {
        "user_id": lambda: generator.random_int(100000, 999999),
        "username": generator.generate_username,
        "email": generator.generate_email,
        "phone": generator.generate_phone,
        "age": lambda: generator.random_int(18, 70),
        "birthday": lambda: generator.faker.date_of_birth(minimum_age=18, maximum_age=70).isoformat(),
        "address": generator.generate_address,
        "company": generator.generate_company,
        "job": generator.generate_job,
        "credit_score": lambda: generator.random_int(300, 850),
        "is_active": generator.random_bool,
        "registered_at": lambda: generator.generate_date_time(start_date="-5y").isoformat(),
        "last_login": lambda: generator.generate_date_time(start_date="-30d").isoformat(),
        "tags": lambda: generator.generate_list(
            lambda: generator.random_choice(["vip", "new", "premium", "trial", "banned"]),
            min_len=0,
            max_len=3
        ),
        "profile": lambda: {
            "avatar": generator.faker.image_url(),
            "bio": generator.generate_paragraph(nb_sentences=2),
            "website": generator.generate_url()
        }
    }

    # 同步批量生成 1000 条用户数据
    print("【同步生成】用户数据...")
    users = generator.batch_generate(user_schema, count=1000, show_progress=True)
    print(f"✓ 生成 {len(users)} 条用户数据")
    print(f"  样例: {json.dumps(users[0], ensure_ascii=False, indent=2)[:200]}...")

    # 导出示例
    output_dir = settings.project_root/"output/data_faker"
    output_dir.mkdir(exist_ok=True)
    generator.export_to_json(users, output_dir / "users.json")
    generator.export_to_csv(users, output_dir / "users.csv")


    # 异步生成订单数据（修复 UUID 问题）
    async def demo_async():
        print("\n【异步生成】订单数据...")
        orders_schema = {
            "order_id": lambda: f"ORD{generator.generate_uuid(short=True)}",  # 修复点：使用专用方法
            "user_id": lambda: generator.random_int(100000, 999999),
            "product_name": generator.faker.catch_phrase,
            "quantity": lambda: generator.random_int(1, 10),
            "unit_price": lambda: round(generator.random_float(10.0, 1000.0), 2),
            "total_amount": lambda: round(generator.random_float(50.0, 5000.0), 2),
            "currency": lambda: "CNY",
            "status": lambda: generator.random_choice(
                ["pending", "paid", "shipped", "delivered", "cancelled"],
                weights=[0.05, 0.35, 0.4, 0.15, 0.05]
            ),
            "payment_method": lambda: generator.random_choice(
                ["alipay", "wechat", "credit_card", "debit_card"],
                weights=[0.5, 0.3, 0.15, 0.05]
            ),
            "ip_address": generator.generate_ipv4,
            "user_agent": lambda: generator.faker.user_agent(),
            "created_at": lambda: generator.generate_date_time(start_date="-30d").isoformat(),
            "updated_at": lambda: generator.generate_date_time(start_date="-7d").isoformat()
        }

        orders = await generator.batch_generate_async(
            orders_schema,
            count=500,
            concurrency=20,
            show_progress=True
        )
        print(f"✓ 异步生成 {len(orders)} 条订单数据")
        print(f"  样例 order_id: {orders[0]['order_id']}")

        # 导出
        generator.export_to_json(orders, output_dir / "orders.json")
        generator.export_to_csv(orders, output_dir / "orders.csv")


    # 运行异步示例
    asyncio.run(demo_async())


    # 自定义策略示例：序列化ID生成器
    @dataclass
    class SequentialIdStrategy:
        prefix: str = "SEQ"
        counter: int = 0

        def generate(self, context: Optional[Dict[str, Any]] = None) -> str:
            self.counter += 1
            return f"{self.prefix}{self.counter:06d}"


    generator.register_strategy("user_seq_id", SequentialIdStrategy(prefix="USR"))
    print(f"\n【自定义策略】序列化ID: {generator.use_strategy('user_seq_id')}")
    print(f"【自定义策略】序列化ID: {generator.use_strategy('user_seq_id')}")

    print(f"\n✅ 所有测试数据已生成并导出至 {output_dir.resolve()} 目录")
