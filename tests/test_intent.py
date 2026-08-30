from intent.recognizer import recognize_intent_rule_based


def test_rule_based_intent():
    assert recognize_intent_rule_based("统计各品类销售额") == "bar"
    assert recognize_intent_rule_based("销售额趋势变化") == "line"
    assert recognize_intent_rule_based("各品类占比") == "pie"
    assert recognize_intent_rule_based("订单明细列表") == "table"
    assert recognize_intent_rule_based("随便问问") == "table"
    print("✅ 意图识别测试通过")
