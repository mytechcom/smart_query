from nl2sql.validator import validate_sql


def test_sql_validator():
    assert validate_sql("SELECT * FROM orders") is True
    assert validate_sql("select 1") is True
    assert validate_sql("") is False
    assert validate_sql("DROP TABLE orders") is False
    assert validate_sql("DELETE FROM orders") is False
    assert validate_sql("UPDATE orders SET status='1'") is False
    assert validate_sql("SELECT *; DROP TABLE orders") is False
    print("✅ SQL 校验测试通过")
