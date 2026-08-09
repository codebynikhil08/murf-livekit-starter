import os
import pytest
from src.db import init_db, get_caller_info, save_caller_info

@pytest.fixture
def temp_db(tmp_path):
    db_file = os.path.join(tmp_path, "test_users.db")
    init_db(db_file)
    return db_file

def test_save_and_get_caller_info(temp_db):
    # Lookup non-existent user
    result = get_caller_info("Ramesh", db_path=temp_db)
    assert result is None

    # Save caller facts
    saved = save_caller_info(
        name="Ramesh",
        user_id="user_ramesh",
        language_preference="Hindi",
        facts={"crop": "cotton", "land_acres": 5, "district": "Yavatmal", "irrigation": "drip"},
        db_path=temp_db,
    )
    assert saved["name"] == "Ramesh"
    assert saved["facts"]["crop"] == "cotton"
    assert saved["facts"]["district"] == "Yavatmal"

    # Retrieve by name
    retrieved = get_caller_info("Ramesh", db_path=temp_db)
    assert retrieved is not None
    assert retrieved["user_id"] == "user_ramesh"
    assert retrieved["facts"]["land_acres"] == 5

    # Update caller info
    save_caller_info(
        name="Ramesh",
        user_id="user_ramesh",
        facts={"pest_control": "neem oil spray"},
        db_path=temp_db,
    )
    updated = get_caller_info("user_ramesh", db_path=temp_db)
    assert updated["facts"]["crop"] == "cotton"
    assert updated["facts"]["pest_control"] == "neem oil spray"
