from sapient_msg.testing.messages import deepsplit, registration_message


def test_deepsplit():
    assert deepsplit() == {}
    assert deepsplit(a=1) == {"a": 1}
    assert deepsplit(a__b=1) == {"a": {"b": 1}}
    assert deepsplit(a__b__c=1, a__b__d=2) == {"a": {"b": {"c": 1, "d": 2}}}


def test_registration_message():
    assert registration_message(node_id="2", registration__name="other name").node_id == "2"
    assert (
        registration_message(node_id="2", registration__name="other name").registration.name
        == "other name"
    )
