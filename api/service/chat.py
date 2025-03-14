from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
from api.utils.log_decorator import log
from agent.workflow import build_graph
from langgraph.types import Command
from langgraph.types import StateSnapshot
from api.model.api.test_result import CreateTestResultRequest
from api.service.test_result import TestResultService
from agent.interview_response import InterviewResult
from loguru import logger
from api.service.test import TestService
from langgraph.graph import START


class ChatService:
    """聊天服务类"""
    
    def __init__(self):
        """初始化聊天服务"""
        self.workflow = build_graph()
        self.model_name = "claude-3-5-sonnet"
        self.test_service = TestService()  # 添加 TestService 实例
    
    @log
    async def start_chat(
        self,
        user_id: str,
        test_id: str,
        job_title: str,
        examination_points: str,
        test_time: int,
        language: str,
        difficulty: str
    ) -> Dict[str, Any]:
        """
        开始聊天
        
        Args:
            user_id: 用户ID
            test_id: 测试ID
            job_title: 职位名称
            examination_points: 考查要点
            test_time: 测试时间（分钟）
            language: 语言
            difficulty: 难度
            
        Returns:
            Dict: 包含第一个问题的信息
        """
        inputs = {
            "start_time": datetime.now(),
            "end_time": datetime.now(),
            "messages": [],
            "job_title": job_title,
            "knowledge_points": examination_points,
            "interview_time": test_time,
            "language": language,
            "difficulty": difficulty
        }

        config = {
            "configurable": {
                "thread_id": test_id, 
                "user_id": user_id
            },
            "model_name": self.model_name,
            # "model_name": "gpt-4o",
            # "model_name": "deepseek-v3",
        }

        # check if the test exists
        current: StateSnapshot = self.workflow.get_state(config)
        if current:
            # workflow found
            (next,) = current.next if current.next else (None,)
            feedback = current.values["feedback"] if "feedback" in current.values.keys() else None
            question_id = str(uuid4())
            type = "question"
            if next is None:
                if "interview_result" in current.values.keys():
                    logger.info(f"start chat, current next is None and interview_result exists")
                    # workflow ends
                    # load all messages from the test
                    # return is_over = true
                    if "qa_history" in current.values.keys():
                        qa_history=[{"question": q, "answer": a, "summary": s} for (q, a, s) in current.values["qa_history"]]
                    else:
                        qa_history = []

                    return {
                        "feedback": feedback,
                        "question_id": question_id,
                        "type": type,
                        "is_over": True,
                        "qa_history": qa_history
                    }
                else:
                    # normal start the workflow
                    pass
            elif next == "analyze_answer":
                logger.info(f"start chat, current next is analyze_answer")
                # load all messages from the test
                # wait for user answer
                # return is_over = false
                if "qa_history" in current.values.keys():
                    qa_history=[{"question": q, "answer": a, "summary": s} for (q, a, s) in current.values["qa_history"]]
                else:
                    qa_history = []

                return {
                    "feedback": feedback,
                    "question_id": question_id,
                    "type": type,
                    "is_over": False,
                    "qa_history": qa_history
                }
            elif next != START:
                logger.info(f"start chat, current next is {next}")
                # resume the workflow
                # load all messages from the test
                events = self.workflow.invoke(None, config=config)
                for event in events:
                    pass

                # get the snapshot state (next question is in the snapshot)
                snapshot = self.workflow.get_state(config)
                if snapshot.next:                    
                    # show the question to user
                    # wait for user answer
                    feedback = snapshot.values["feedback"]
                    is_over = False
                else:
                    # workflow has no next, end
                    is_over = True

                if "qa_history" in current.values.keys():
                    qa_history=[{"question": q, "answer": a, "summary": s} for (q, a, s) in current.values["qa_history"]]
                else:
                    qa_history = []

                return {
                    "feedback": feedback,
                    "question_id": str(uuid4()),  # TODO: 需要从snapshot中获取
                    "type": "question",
                    "is_over": is_over,
                    "qa_history": qa_history
                }

        # new workflow
        # start the interview, generate the first question
        events = self.workflow.stream(inputs, config=config, stream_mode="values")
        for event in events:
            pass

        snapshot: StateSnapshot = self.workflow.get_state(config)
        if snapshot.next:                    
            # show the question to user
            feedback = snapshot.values["feedback"]
            is_over = False
        else:
            is_over = True

        return {
            "feedback": feedback,
            "question_id": str(uuid4()),  # TODO: 需要从snapshot中获取
            "type": "question",
            "is_over": is_over
        }
    
    @log
    async def process_answer(
        self,
        user_id: str,
        test_id: str,
        question_id: str,
        user_answer: str
    ) -> Dict[str, Any]:
        """
        处理用户回答
        
        Args:
            user_id: 用户ID
            test_id: 测试ID
            question_id: 问题ID
            user_answer: 用户回答
            
        Returns:
            Dict: 包含下一个问题或反馈的信息
        """
        config = {
            "configurable": {
                "thread_id": test_id, 
                "user_id": user_id
            },
            "model_name": self.model_name,
            # "model_name": "gpt-4o",
            # "model_name": "deepseek-v3",
        }

        # resume the interview workflow
        # pass user answer and get the result
        # then generate next question
        events = self.workflow.invoke(Command(resume="Go ahead", update={"user_answer": user_answer}), config=config)
        for event in events:
            pass

        # get the snapshot state (next question is in the snapshot)
        snapshot = self.workflow.get_state(config)
        feedback = snapshot.values["feedback"]

        # check if the interview is over
        if "interview_result" in snapshot.values.keys():
            # call test result service to update interview result
            # async call
            interview_result: InterviewResult = snapshot.values["interview_result"]  
            logger.info(f"Interview is over, call test result service to update interview result {interview_result.model_dump_json(indent=2)}")

            # 保存测试结果
            test_result_service = TestResultService()
            request = CreateTestResultRequest(
                test_id=test_id,
                user_id=user_id,
                summary=interview_result.summary,
                score=interview_result.score,
                question_number=interview_result.total_question_number,
                correct_number=interview_result.correct_question_number,
                elapse_time=interview_result.interview_time,
                qa_history=[{"question": q, "answer": a, "summary": s} for (q, a, s) in snapshot.values["qa_history"]]
            )
            await test_result_service.complete_test_result(request)

            # 更新测试状态为已完成
            await self.test_service.update_test_status_to_completed(test_id)

            is_over = True
        else:
            is_over = False

        return {
            "feedback": feedback,
            "question_id": str(uuid4()),  # TODO: 需要从snapshot中获取
            "type": "question",
            "is_over": is_over
        }
