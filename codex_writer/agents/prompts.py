import json


def build_agent_prompt(agent: str, payload: dict) -> dict:
    system_prompt = f"{agent}: 只能产出指定工件；不能直接写入 state.json、index.sqlite、commits/；不能自行判定 accepted。"
    task_prompt = json.dumps(payload, ensure_ascii=False)
    return {"system_prompt": system_prompt, "task_prompt": task_prompt}