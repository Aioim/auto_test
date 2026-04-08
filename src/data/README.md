# Data 模块文档

## 模块概述

Data 模块是一个功能强大的测试数据管理工具集，提供了以下核心功能：

- **YAML 测试数据加载**：支持从 YAML 文件加载和验证测试数据
- **测试数据生成**：基于 Faker 库的高性能测试数据生成器
- **数据导出**：支持将生成的数据导出为 JSON 和 CSV 格式

## 安装依赖

```bash
# 安装基础依赖
pip install pyyaml faker

# 安装可选依赖（用于进度条显示）
pip install tqdm
```

## 核心功能

### 1. YAML 测试数据加载

Data 模块提供了两种 YAML 加载器，用于从 YAML 文件加载测试数据：

#### 1.1 标准加载器 (`data_loader.py`)

**功能**：
- 加载 YAML 文件并返回标准化的数据结构
- 自动处理单个用例（字典）和多个用例（列表）
- 跳过无效数据并记录警告
- 捕获异常并记录日志

**返回结构**：
```python
{
    "group_name": [
        {"field1": "value1", "field2": "value2"},  # 用例 1
        {"field1": "value3", "field2": "value4"}   # 用例 2
    ]
}
```

#### 1.2 严格加载器 (`yaml_cases_loader.py`)

**功能**：
- 严格验证 YAML 格式
- 限制文件大小（最大 10MB，防 DoS 攻击）
- 提供详细的错误信息
- 标准化数据结构

**异常**：
- `FileNotFoundError`：文件不存在或不是文件
- `InvalidYamlFormatError`：YAML 格式验证失败

### 2. 测试数据生成器 (`TestDataGenerator`)

**功能**：
- **基础类型生成**：随机字符串、整数、浮点数、布尔值等
- **业务数据生成**：用户名、邮箱、电话、地址、公司名称、职位等
- **复杂结构生成**：字典、列表等
- **批量生成**：支持同步和异步批量生成数据
- **自定义策略**：可注册自定义数据生成策略
- **数据导出**：支持导出为 JSON 和 CSV 格式

**特点**：
- 基于 Faker 库，支持多语言（默认中文）
- 支持并发控制（异步生成）
- 提供详细的日志记录
- 支持数据导出为标准格式

## 使用示例

### 1. 加载 YAML 测试数据

#### 使用标准加载器

```python
from pathlib import Path
from utils.data import load_yaml_file

# 加载 YAML 文件
data = load_yaml_file(Path("test_data/login_page.yaml"))

# 访问测试数据
login_cases = data.get("login_page_case", [])
for case in login_cases:
    print(f"Username: {case.get('username')}, Password: {case.get('password')}")
```

#### 使用严格加载器

```python
from pathlib import Path
from utils.data.yaml_cases_loader import load_yaml_file, InvalidYamlFormatError

try:
    # 加载 YAML 文件
data = load_yaml_file(Path("test_data/login_page.yaml"))
    print("加载成功！")
except InvalidYamlFormatError as e:
    print(f"格式错误: {e}")
except FileNotFoundError as e:
    print(f"文件错误: {e}")
```

### 2. 生成测试数据

#### 基础用法

```python
from utils.data import TestDataGenerator

# 初始化生成器
generator = TestDataGenerator()

# 生成基础类型
print(f"随机字符串: {generator.random_string(length=10)}")
print(f"随机整数: {generator.random_int(1, 100)}")
print(f"随机布尔值: {generator.random_bool()}")

# 生成业务数据
print(f"用户名: {generator.generate_username()}")
print(f"邮箱: {generator.generate_email()}")
print(f"电话: {generator.generate_phone()}")
print(f"地址: {generator.generate_address()}")
print(f"UUID: {generator.generate_uuid()}")
print(f"短 UUID: {generator.generate_uuid(short=True)}")
```

#### 生成复杂结构

```python
from utils.data import TestDataGenerator

generator = TestDataGenerator()

# 生成用户数据 schema
user_schema = {
    "user_id": lambda: generator.random_int(100000, 999999),
    "username": generator.generate_username,
    "email": generator.generate_email,
    "phone": generator.generate_phone,
    "age": lambda: generator.random_int(18, 70),
    "is_active": generator.random_bool,
    "registered_at": lambda: generator.generate_date_time(start_date="-5y").isoformat(),
    "tags": lambda: generator.generate_list(
        lambda: generator.random_choice(["vip", "new", "premium"]),
        min_len=0, max_len=3
    )
}

# 生成单个用户
user = generator.generate_dict(user_schema)
print(f"单个用户: {user}")

# 批量生成用户（同步）
users = generator.batch_generate(user_schema, count=10, show_progress=True)
print(f"生成了 {len(users)} 个用户")

# 导出数据
generator.export_to_json(users, Path("output/users.json"))
generator.export_to_csv(users, Path("output/users.csv"))
```

#### 异步批量生成

```python
import asyncio
from pathlib import Path
from utils.data import TestDataGenerator

generator = TestDataGenerator()

async def generate_orders():
    # 生成订单数据 schema
    orders_schema = {
        "order_id": lambda: f"ORD{generator.generate_uuid(short=True)}",
        "user_id": lambda: generator.random_int(100000, 999999),
        "product_name": generator.faker.catch_phrase,
        "quantity": lambda: generator.random_int(1, 10),
        "total_amount": lambda: round(generator.random_float(50.0, 5000.0), 2),
        "status": lambda: generator.random_choice(
            ["pending", "paid", "shipped", "delivered"],
            weights=[0.1, 0.3, 0.4, 0.2]
        ),
        "created_at": lambda: generator.generate_date_time(start_date="-30d").isoformat()
    }

    # 异步批量生成订单
    orders = await generator.batch_generate_async(
        orders_schema,
        count=100,
        concurrency=20,
        show_progress=True
    )
    print(f"异步生成了 {len(orders)} 个订单")

    # 导出数据
    generator.export_to_json(orders, Path("output/orders.json"))

# 运行异步生成
asyncio.run(generate_orders())
```

#### 自定义生成策略

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
from utils.data import TestDataGenerator

# 定义自定义策略
@dataclass
class SequentialIdStrategy:
    prefix: str = "SEQ"
    counter: int = 0

    def generate(self, context: Optional[Dict[str, Any]] = None) -> str:
        self.counter += 1
        return f"{self.prefix}{self.counter:06d}"

# 初始化生成器
generator = TestDataGenerator()

# 注册自定义策略
generator.register_strategy("user_seq_id", SequentialIdStrategy(prefix="USR"))

# 使用自定义策略
print(f"序列化 ID: {generator.use_strategy('user_seq_id')}")
print(f"序列化 ID: {generator.use_strategy('user_seq_id')}")
```

## API 参考

### 1. YAML 加载函数

#### `load_yaml_file(file_path: Path) -> Dict[str, List[Dict[str, Any]]]`

加载 YAML 文件并返回标准化的测试数据结构。

**参数**：
- `file_path`：YAML 文件的路径

**返回值**：
- 字典，键为组名，值为用例列表

**注意**：
- 该函数是从 `data_loader.py` 导入的，提供了更灵活的加载方式
- 对于更严格的验证，请使用 `yaml_cases_loader.py` 中的同名函数

### 2. TestDataGenerator 类

#### 初始化

```python
def __init__(self, locale: str = 'zh_CN')
```

**参数**：
- `locale`：语言区域，默认 'zh_CN'（中文）

#### 基础类型生成方法

- `random_string(length: int = 10, chars: str = string.ascii_letters + string.digits) -> str`
- `random_int(min_val: int = 0, max_val: int = 100) -> int`
- `random_float(min_val: float = 0.0, max_val: float = 100.0, decimals: int = 2) -> float`
- `random_bool(true_prob: float = 0.5) -> bool`
- `random_choice(choices: List[Any], weights: Optional[List[float]] = None) -> Any`

#### 业务数据生成方法

- `generate_username() -> str`
- `generate_email(domain: Optional[str] = None) -> str`
- `generate_phone() -> str`
- `generate_address() -> str`
- `generate_company() -> str`
- `generate_job() -> str`
- `generate_credit_card() -> Dict[str, str]`
- `generate_ipv4() -> str`
- `generate_mac_address() -> str`
- `generate_url() -> str`
- `generate_text(max_nb_chars: int = 200) -> str`
- `generate_sentence(nb_words: int = 6) -> str`
- `generate_paragraph(nb_sentences: int = 3) -> str`
- `generate_date_time(start_date: str = "-30y", end_date: str = "now", tzinfo: Optional[timezone] = None) -> datetime`
- `generate_date(pattern: str = "%Y-%m-%d") -> str`
- `generate_time(pattern: str = "%H:%M:%S") -> str`
- `generate_uuid(short: bool = False, upper: bool = True) -> str`

#### 复杂结构生成方法

- `generate_dict(schema: Dict[str, Callable[[], Any]], count: int = 1) -> Union[Dict[str, Any], List[Dict[str, Any]]]`
- `generate_list(item_generator: Callable[[], Any], min_len: int = 1, max_len: int = 10) -> List[Any]`

#### 批量生成方法

- `batch_generate(schema: Dict[str, Callable[[], Any]], count: int = 100, show_progress: bool = True) -> List[Dict[str, Any]]`
- `batch_generate_async(schema: Dict[str, Callable[[], Any]], count: int = 100, concurrency: int = 10, show_progress: bool = True) -> List[Dict[str, Any]]`

#### 自定义策略方法

- `register_strategy(name: str, strategy: GeneratorStrategy) -> None`
- `use_strategy(name: str, context: Optional[Dict[str, Any]] = None) -> Any`

#### 数据导出方法

- `export_to_json(data: Union[Dict, List], filepath: Path, indent: int = 2, ensure_ascii: bool = False) -> None`
- `export_to_csv(data: List[Dict], filepath: Path, fieldnames: Optional[List[str]] = None) -> None`

### 3. InvalidYamlFormatError 类

`InvalidYamlFormatError` 是一个异常类，用于在 YAML 格式验证失败时抛出详细的错误信息。

## 最佳实践

### 1. YAML 测试数据结构

推荐的 YAML 测试数据结构：

```yaml
# 单个用例
login_success:
  username: admin
  password: password123
  expected: success

# 多个用例
login_failures:
  - username: admin
    password: wrongpassword
    expected: invalid_password
  - username: non_existent
    password: password123
    expected: user_not_found
  - username: ""
    password: ""
    expected: empty_credentials
```

### 2. 数据生成最佳实践

- **使用 Schema**：定义清晰的数据生成 schema，提高代码可读性和维护性
- **合理设置并发**：异步生成时，根据系统资源设置适当的并发数
- **使用权重**：在随机选择时使用权重，模拟真实场景的分布
- **导出为标准格式**：将生成的数据导出为 JSON 或 CSV，方便后续分析和使用
- **注册自定义策略**：对于复杂的数据生成需求，使用自定义策略

### 3. 性能优化

- **批量生成**：对于大量数据，使用 `batch_generate` 或 `batch_generate_async`
- **异步生成**：对于 I/O 密集型操作，使用异步生成提高性能
- **进度显示**：生成大量数据时，启用进度显示，提升用户体验

## 依赖

- **pyyaml**：用于解析 YAML 文件
- **faker**：用于生成测试数据
- **tqdm**：用于显示生成进度（可选）
- **python-dateutil**：用于日期时间处理（Faker 依赖）

## 安装

```bash
pip install pyyaml faker tqdm
```

## 总结

Data 模块是一个功能强大、灵活易用的测试数据管理工具，它提供了：

- 方便的 YAML 测试数据加载和验证
- 丰富的测试数据生成能力
- 高效的批量数据生成
- 灵活的自定义策略机制
- 标准的数据导出功能

通过使用 Data 模块，您可以：
- 更有效地管理测试数据
- 生成真实、多样化的测试数据
- 提高测试的覆盖率和可靠性
- 减少手动数据准备的工作量

---

**注意**：模块中存在命名冲突，`load_yaml_file` 函数被从两个不同的文件导入。在使用时，默认导入的是 `data_loader.py` 中的实现。如果需要使用严格验证版本，请直接从 `yaml_cases_loader` 模块导入。