"""AI Agent 计划层（阶段 1：任务拆解 → 顺序执行 → 综合回答）

设计（演进式，不引入多 Agent 框架）：
- should_plan：启发式判断问题是否需要“任务拆解”；
- build_plan：一次轻量 LLM 调用，把用户问题拆成 1~5 个有序子任务（JSON）；
- run_planned：每个子任务用 run_agent 独立执行（可携带上一步产出），
  子任务之间的结论与来源逐条累积，最后由一次无工具综合生成最终回答。

用途：多意图问题（知识库 + 实时参数 + 联网对比等）自动并行/串行拆解，
是阶段 2“supervisor + 子 Agent”的落点；子任务以文本上下文协作，不跨进程。
"""
import json
import logging
import re
from typing import Any, Optional

from app.core.config import settings
from app.services import agent

logger = logging.getLogger(__name__)

MAX_STEPS = 5
MAX_STEP_CHARS = 400          # 每个子任务产物进入综合的最大长度
_PLAN_RE = re.compile(r"\{.*\}", re.S)
_PLAN_HINTS = (
    "复杂意图词：同时/并且/还要/对比/比较/查一下…再…/结合/顺便/另外；"
    "或单句含多个独立疑问（？ 出现 ≥2 次）。"
)


def _plan_json_mode(messages: list[dict]) -> str:
    """请求模型仅输出 JSON 计划（DeepSeek 等支持 json_object 时用）"""
    from openai import OpenAI

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url or None)
    sys = (
        "你是任务规划器。请把用户问题拆成 1~5 个有序子任务步骤，只输出 JSON："
        '{"steps":[{"goal":"子任务目标(一句话，面向执行智能体)",'
        '"tools":["kb"|"web"|"live"|"none"]}]}'
        "。tools 说明：kb=知识库检索、web=联网搜索/抓取、live=天气/IP/系统等实时参数、"
        "none=无需工具。不要输出任何多余文字。"
    )
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "system", "content": sys}] + [
            m for m in messages if m.get("role") != "assistant"
        ],
        temperature=0.2,
        max_tokens=600,
    )
    text = (resp.choices[0].message.content or "").strip()
    m = _PLAN_RE.search(text)
    return m.group(0) if m else text


def should_plan(question: str, tools_enabled: bool = True, mode: str = "auto") -> bool:
    """启发式：是否需要计划层（mode=simple 强制关闭）"""
    if mode == "simple":
        return False
    if mode == "plan":
        return bool(question.strip()) and tools_enabled
    if not tools_enabled or not question:
        return False
    q = question.strip()
    if len(q) < 12:
        return False
    multi_marks = q.count("？") + q.count("?")
    if multi_marks >= 2:
        return True
    return any(k in q for k in ("同时", "并且", "还要", "对比", "比较",
                                "查一下", "顺便", "结合", "另外", "以及"))


def build_plan(question: str) -> list[dict[str, Any]]:
    """生成计划步骤：[{goal, tools}]；失败返回 [{goal: 原问题, tools:[none]}]"""
    try:
        text = _plan_json_mode([{"role": "user", "content": question}])
        data = json.loads(text)
        steps = data.get("steps") if isinstance(data, dict) else data
        if not isinstance(steps, list):
            raise ValueError("steps 非列表")
        out: list[dict[str, Any]] = []
        for s in steps[:MAX_STEPS]:
            if isinstance(s, dict) and str(s.get("goal") or "").strip():
                tools = s.get("tools")
                if not isinstance(tools, list):
                    tools = ["none"]
                out.append({"goal": str(s["goal"]).strip(), "tools": [str(t) for t in tools]})
        return out or [{"goal": question, "tools": ["none"]}]
    except Exception as exc:  # noqa: BLE001
        logger.warning("build_plan 失败（退回单步）: %s", exc)
        return [{"goal": question, "tools": ["none"]}]


def run_planned(
    messages: list[dict],
    question: str,
    steps: list[dict[str, Any]],
    temperature: float = 0.7,
    tools_enabled: bool = True,
    client_context: Optional[dict] = None,
    rag_context: Optional[dict] = None,
) -> tuple[str, list[dict[str, Any]]]:
    """按计划逐子任务执行并综合。

    返回 (answer, step_records)，step_records 供前端展示“执行步骤”进度。
    """
    prior: list[str] = []          # 已完成子任务的产物
    records: list[dict[str, Any]] = []
    model = settings.llm_model

    for i, step in enumerate(steps, start=1):
        goal = str(step.get("goal") or "")
        goal_msgs: list[dict] = [{"role": "user", "content": (
            f"子任务 {i}/{len(steps)}：{goal}\n"
            "请只完成这个子任务，把结论整理成要点（≤200 字）；"
            "用到实时/联网/知识库信息时先调用相应工具，并标注来源。"
            + (f"\n此前子任务结论（可参考）：\n{chr(10).join(prior[-3:])}" if prior else "")
        )}]
        try:
            text, model, _ = agent.run_agent(
                goal_msgs,
                temperature=min(temperature, 0.4),
                tools_enabled=tools_enabled,
                client_context=client_context,
                rag_context=rag_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("子任务 %s 执行失败: %s", i, exc)
            text = f"（子任务 {i} 未完成：{type(exc).__name__}: {exc}）"
        record = {"goal": goal, "summary": text[: MAX_STEP_CHARS]}
        records.append(record)
        if text:
            prior.append(f"[步骤{i}]{goal}\n{text[:MAX_STEP_CHARS]}")

    # 综合：基于全部子任务产物 + 原始问题，一次无工具回答
    digest = "\n\n".join(f"#### {r['goal']}\n{r['summary']}" for r in records)
    final_msgs = [dict(m) for m in messages]
    if digest:
        final_msgs = [{"role": "system", "content": (
            "以下是针对该问题的已执行子任务结论（知识库片段/联网资料/实时数据均已归集）：\n"
            f"{digest}\n\n请综合上述结论回答用户问题：结构清晰、标注关键来源，"
            "不要重复执行工具；信息不足时如实说明。"
        )}] + final_msgs
    answer, model, _ = agent.run_agent(
        final_msgs,
        temperature=temperature,
        tools_enabled=False,        # 综合阶段不再调用工具
        client_context=client_context,
        rag_context=rag_context,
    )
    return (answer or "").strip(), records
