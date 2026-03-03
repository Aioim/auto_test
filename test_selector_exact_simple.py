"""
测试Selector类的exact属性

验证exact属性是否正常工作，包括属性设置和formatted方法
"""
from src.utils.common.selector_helper import Selector


def test_selector_exact_property():
    """
    测试Selector类的exact属性
    """
    print("=== 测试Selector类的exact属性 ===")
    
    # 创建一个带有exact=True的Selector
    exact_selector = Selector(text="测试文本", exact=True)
    print(f"✓ 创建了exact=True的Selector")
    print(f"  exact属性值: {exact_selector.exact}")
    assert exact_selector.exact == True, "exact属性应该为True"
    
    # 创建一个带有exact=False的Selector
    non_exact_selector = Selector(text="测试文本", exact=False)
    print(f"✓ 创建了exact=False的Selector")
    print(f"  exact属性值: {non_exact_selector.exact}")
    assert non_exact_selector.exact == False, "exact属性应该为False"
    
    # 创建一个默认exact值的Selector
    default_selector = Selector(text="测试文本")
    print(f"✓ 创建了默认exact值的Selector")
    print(f"  exact属性值: {default_selector.exact}")
    assert default_selector.exact == False, "exact属性默认值应该为False"
    
    # 测试formatted方法是否保留exact属性
    formatted_selector = exact_selector.formatted()
    print(f"✓ 测试formatted方法")
    print(f"  formatted后exact属性值: {formatted_selector.exact}")
    assert formatted_selector.exact == True, "formatted方法应该保留exact属性"
    
    # 测试带有其他属性的Selector
    complex_selector = Selector(
        role="button",
        role_name="提交",
        exact=True,
        css=".submit-button"
    )
    print(f"✓ 创建了带有多个属性的Selector")
    print(f"  exact属性值: {complex_selector.exact}")
    assert complex_selector.exact == True, "exact属性应该为True"
    
    # 测试formatted方法对复杂Selector的处理
    formatted_complex = complex_selector.formatted()
    print(f"✓ 测试复杂Selector的formatted方法")
    print(f"  formatted后exact属性值: {formatted_complex.exact}")
    assert formatted_complex.exact == True, "formatted方法应该保留exact属性"
    
    print("\n✓ 所有属性测试通过!")
    return True


def run_test():
    """
    运行测试
    """
    print("开始测试Selector类的exact属性...")
    
    success = test_selector_exact_property()
    
    print(f"\n测试完成: {'通过' if success else '失败'}")
    
    return success


if __name__ == "__main__":
    success = run_test()
    import sys
    sys.exit(0 if success else 1)