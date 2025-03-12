import pytest
from datetime import datetime, UTC
from api.model.db.test import Test, TestStatus
from api.repositories.test_repository import TestRepository
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up test data after each test"""
    yield
    Test.objects.delete()

@pytest.mark.asyncio
async def test_create_test():
    """Test creating a new test"""
    repo = TestRepository()
    test = Test(
        test_id="test001",
        type="coding",
        language="python",
        difficulty="medium",
        create_date=datetime.now(UTC)
    )
    
    result = await repo.create_test(test)
    assert result.test_id == "test001"
    assert result.type == "coding"

@pytest.mark.asyncio
async def test_get_test():
    """Test getting a test by ID"""
    # First create a test
    repo = TestRepository()
    test = Test(
        test_id="test001",
        type="coding",
        language="python",
        difficulty="medium",
        create_date=datetime.now(UTC)
    ).save()
    
    # Then try to get it
    result = await repo.get_test_by_id("test001")
    assert result is not None
    assert result.test_id == "test001"

@pytest.mark.asyncio
async def test_update_test_status():
    # 准备测试数据
    test_id = "test_id_123"
    new_status = TestStatus.COMPLETED

    # 模拟 MongoDB 集合
    mock_collection = MagicMock()
    mock_collection.find_one_and_update.return_value = {
        "test_id": test_id,
        "status": new_status.value,
        "update_date": datetime.now(UTC),
        "close_date": datetime.now(UTC)
    }

    # 使用 patch 模拟 Test._get_collection 方法
    with patch("api.repositories.test_repository.Test._get_collection", return_value=mock_collection):
        repository = TestRepository()
        
        # 调用 update_test_status 方法
        updated_test = await repository.update_test_status(test_id, new_status)
        
        # 验证调用参数
        mock_collection.find_one_and_update.assert_called_once_with(
            filter={"test_id": test_id},
            update={
                "$set": {
                    "status": new_status.value,
                    "update_date": mock_collection.find_one_and_update.return_value["update_date"],
                    "close_date": mock_collection.find_one_and_update.return_value["close_date"]
                }
            },
            return_document=True
        )
        
        # 验证返回结果
        assert updated_test is not None
        assert updated_test.test_id == test_id
        assert updated_test.status == new_status.value 