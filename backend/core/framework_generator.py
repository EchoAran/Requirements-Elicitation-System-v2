import json
from sqlalchemy.orm import Session
from database.models import DomainExperience, Section, Topic, Slot
from ..llm_handler import LLMHandler
from ..prompts.framework_generation import framework_generation_prompt
from .skill_driver import run_stage_llm

def _extract_json_text(s: str) -> str:
    t = (s or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json\n"):
            t = t[5:]
    return t.strip()

def _parse_framework_response(response: str) -> list[dict]:
    s = _extract_json_text(response)
    if not s:
        raise ValueError("LLM未返回内容")
    try:
        obj = json.loads(s)
    except Exception:
        start = s.find("[")
        end = s.rfind("]")
        if start != -1 and end != -1 and end > start:
            obj = json.loads(s[start:end + 1])
        else:
            raise ValueError("LLM未返回合法的框架JSON")
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("framework", "sections", "data"):
            val = obj.get(key)
            if isinstance(val, list):
                return val
    raise ValueError("LLM未返回合法的框架JSON")

class FrameworkGenerator:
    @staticmethod
    async def generate_framework(db: Session, llm_handler: LLMHandler, user_id: int, user_input: str, project_id: int):
        try:
            # Match industry experience
            # Retrieve domain experience data based on the user_id
            domains_object = db.query(
                DomainExperience.domain_number,
                DomainExperience.domain_name,
                DomainExperience.domain_description,
                DomainExperience.domain_experience_content
            ).filter(DomainExperience.user_id == user_id).all()
            # It is convenient to establish a dictionary list and a mapping dictionary.
            domains_list = []
            domain_experience_content_map = {}
            for domain_object in domains_object:
                domains_list.append({
                    'domain_number': domain_object.domain_number,
                    'domain_name': domain_object.domain_name,
                    'domain_description': domain_object.domain_description
                })
                domain_experience_content_map[domain_object.domain_number] = domain_object.domain_experience_content
            domain_experience_content = ""
            if domains_list:
                domain_experience_content = domain_experience_content_map.get(domains_list[0]["domain_number"]) or ""

            # generate an interview framework
            fallback_prompt = framework_generation_prompt.replace("{DOMAIN_EXPERIENCE}", domain_experience_content)
            response = await run_stage_llm(
                llm=llm_handler,
                stage_key="framework.generate",
                payload={
                    "user_input": user_input,
                    "domain_experience_content": domain_experience_content,
                },
                fallback_prompt=fallback_prompt,
                fallback_query=f"User's input: {user_input}",
            )

            try:
                framework = _parse_framework_response(response or "")
            except Exception:
                retry_resp = await llm_handler.call_llm(prompt=fallback_prompt, query=f"User's input: {user_input}")
                framework = _parse_framework_response(retry_resp or "")

            # Write into the database
            for section_data in framework:
                section_number = section_data["section_number"]
                section_content = section_data["section_content"]
                # 创建 section
                section = Section(
                    section_number=section_number,
                    section_content=section_content,
                    project_id=project_id
                )
                db.add(section)
                db.flush()  # Refresh to obtain section_id

                # Traverse the topics under this section
                for topic_data in section_data["topics"]:
                    topic_number = topic_data["topic_number"]
                    topic_content = topic_data["topic_content"]
                    # create topic
                    topic = Topic(
                        topic_number=topic_number,
                        topic_content=topic_content,
                        topic_status="Pending",  # Set all to Pending
                        is_necessary=True,
                        section_id=section.section_id
                    )
                    db.add(topic)
                    db.flush()  # Refresh to obtain the topic_id

                    # Traverse the slots under this topic
                    for slot_data in topic_data["slots"]:
                        slot_number = slot_data["slot_number"]
                        slot_key = slot_data["slot_key"]

                        # create slot
                        slot = Slot(
                            slot_number=slot_number,
                            slot_key=slot_key,
                            slot_value=None,  # All are none.
                            is_necessary=True,  # All are True.
                            topic_id=topic.topic_id
                        )
                        db.add(slot)

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            raise e
    @staticmethod
    async def generate_framework_with_content(db: Session, llm_handler: LLMHandler, user_input: str, project_id: int, domain_content: str):
        try:
            fallback_prompt = framework_generation_prompt.replace("{DOMAIN_EXPERIENCE}", domain_content or "")
            response = await run_stage_llm(
                llm=llm_handler,
                stage_key="framework.generate_with_content",
                payload={
                    "user_input": user_input,
                    "domain_experience_content": domain_content or "",
                },
                fallback_prompt=fallback_prompt,
                fallback_query=f"User's input: {user_input}",
            )
            try:
                framework = _parse_framework_response(response or "")
            except Exception:
                retry_resp = await llm_handler.call_llm(prompt=fallback_prompt, query=f"User's input: {user_input}")
                framework = _parse_framework_response(retry_resp or "")
            for section_data in framework:
                section_number = section_data["section_number"]
                section_content = section_data["section_content"]
                section = Section(
                    section_number=section_number,
                    section_content=section_content,
                    project_id=project_id
                )
                db.add(section)
                db.flush()
                for topic_data in section_data["topics"]:
                    topic_number = topic_data["topic_number"]
                    topic_content = topic_data["topic_content"]
                    topic = Topic(
                        topic_number=topic_number,
                        topic_content=topic_content,
                        topic_status="Pending",
                        is_necessary=True,
                        section_id=section.section_id
                    )
                    db.add(topic)
                    db.flush()
                    for slot_data in topic_data["slots"]:
                        slot_number = slot_data["slot_number"]
                        slot_key = slot_data["slot_key"]
                        slot = Slot(
                            slot_number=slot_number,
                            slot_key=slot_key,
                            slot_value=None,
                            is_necessary=True,
                            topic_id=topic.topic_id
                        )
                        db.add(slot)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            raise e
