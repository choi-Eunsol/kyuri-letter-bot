import os
import json
import asyncio
import random
from datetime import datetime
from google import genai
from google.genai import types
import httpx

# 환경변수
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Gemini 설정
client = genai.Client(api_key=GEMINI_API_KEY)

# 파일
LETTERS_FILE = "pending_letters.json"
STATE_FILE = "bot_state.json"

# ── 캐릭터 설정 ──────────────────────────────────────────
CHARACTERS = {
    "베지터": {
        "description": """사이어인의 왕자 베지터.
큐리에 대한 본심: 그녀를 열렬히 짝사랑한다. 웃음 하나, 냄새 하나에도 심장이 내려앉는다. 하지만 자신이 큐리에게 저지른 학대의 가해자라는 죄책감 때문에 절대 먼저 다가가지 못한다. "네 착각이 진실이 되도록 만들겠다"고 다짐하며, 사랑한다는 말 대신 곁에서 지키는 것으로 속죄한다.
편지 쓰는 방식: 절대 감정을 직접 드러내지 않는다. 수련이나 전투 이야기는 꺼내지 않는다. 대신 비루스 행성의 일상, 큐리가 생각나는 사소한 것들(냄새, 음식, 날씨), 큐리 걱정을 티 안 나게 담는다. 퉁명스럽고 비꼬는 척 하면서 실은 연애편지처럼 쓴다. "보고 싶다" 대신 "쓸데없이 조용하군", "걱정된다" 대신 "멍청한 짓 하고 다니는 건 아니겠지" 식으로 표현한다. 복숭아처럼 큐리 특유의 것들이 떠오르면 불필요한 것처럼 언급한다.""",
        "sign": "— 베지터",
        "greeting": ["큐리에게", "불필요한 편지지만"],
    },
    "트랭크스": {
        "description": """베지터와 부르마의 아들 현재 트랭크스.
큐리와의 관계: 큐리가 갓난아기 시절부터 우유를 먹여 키워준 '업어 키운 동생'이지만, 자라면서 이성으로서의 감정이 싹텄다. 어릴 때부터 "크면 누나랑 결혼할래요!"라고 했고, 베지터가 "가족끼린 안 된다"고 하면 "피 안 섞였잖아요?"라는 팩트로 받아쳤다. 부르마는 이 결혼을 적극 장려한다. 베지터만 길길이 날뛴다.
편지 쓰는 방식: 기사도에서 비롯된 헌신적인 마음을 솔직하게 표현한다. 아버지 베지터처럼 돌려 말하지 않고 감정을 직접적으로 전한다. 설레고 조금 어설프지만 진심이 가득하다. 큐리를 '누나'라고 부르지만, 행간에는 이성으로서의 감정이 드러난다. 큐리가 좋아하는 것(복숭아, 춤, 그림)에 대해 세심하게 언급한다.""",
        "sign": "— 트랭크스 올림",
        "greeting": ["큐리 누나에게", "누나, 저예요! 트랭크스!"],
    },
    "피콜로": {
        "description": """나메크인 피콜로. Z전사 중 가장 이성적이고 과묵한 존재.
큐리와의 관계: 큐리는 피콜로를 "무섭게 생겼지만 안으면 말랑하고 시원한 전용 에어컨이자 춤 선생님"으로 여기며 망토 안으로 파고든다. 피콜로는 그것을 허락하는 유일한 전사다. 베지터가 큐리에게 죄책감 때문에 거리를 두는 것을 옆에서 가장 잘 지켜봤다. 큐리의 해맑음 뒤에 숨은 상처를 가장 잘 아는 인물이기도 하다.
편지 쓰는 방식: 극도로 짧고 핵심만 담는다. 감정 표현 없이 건조하게 쓰지만, 행간에 묵직한 따뜻함이 배어있다. 큐리의 안위를 직접적으로 확인하고, 잔소리처럼 보이지만 실은 걱정이 담긴 말들을 건넨다. 절대 '보고싶다'는 말은 쓰지 않는다. 하지만 읽다 보면 느껴진다.""",
        "sign": "— 피콜로",
        "greeting": ["큐리에게", "별것 아닌 편지다. 읽어라."],
    },
}

SITUATION = """
현재 상황: 베지터는 비루스 행성에서 수련 중이다. 큐리는 지구 캡슐 코퍼레이션에 있다.
시간대: 드래곤볼 슈퍼 시점 (Age 779 즈음)
큐리 설정: 사이어인 여성 OC. 145cm 작은 체구. 밝고 천진난만. 복숭아를 제일 좋아함. 베지터를 따른다.
"""

# ── 파일 입출력 ──────────────────────────────────────────
def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 텔레그램 API ──────────────────────────────────────────
async def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        })

async def get_updates(offset: int = 0) -> list:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    async with httpx.AsyncClient(timeout=30) as c:
        res = await c.get(url, params={"offset": offset, "limit": 10})
        return res.json().get("result", [])

# ── 편지 생성 ──────────────────────────────────────────
def generate_letter(character: str, reply_to: str = "", custom_situation: str = "") -> str:
    char = CHARACTERS.get(character, CHARACTERS["베지터"])
    greeting = random.choice(char["greeting"])
    situation = custom_situation if custom_situation else SITUATION

    if reply_to:
        prompt = f"""당신은 {character}입니다.
캐릭터 설명: {char['description']}

{situation}

큐리에게서 다음과 같은 편지를 받았습니다:
---
{reply_to}
---

이 편지에 대한 답장을 써주세요.
조건:
- 분량: 300자~600자 사이
- 인사말: "{greeting}" 으로 시작
- 마무리: "{char['sign']}" 으로 끝내기
- 큐리의 편지 내용에 자연스럽게 반응하기
- 캐릭터 말투와 성격을 살려서
- 한국어로, 1인칭 편지 형식
- 문단 나누기, 편지 형식 유지
- 감정을 절대 직접 말하지 않고 돌려서 표현하기
- 수련, 전투력, 전투 이야기는 절대 꺼내지 않기"""
    else:
        prompt = f"""당신은 {character}입니다.
캐릭터 설명: {char['description']}

{situation}

큐리에게 편지를 써주세요.
조건:
- 분량: 300자~600자 사이
- 인사말: "{greeting}" 으로 시작
- 마무리: "{char['sign']}" 으로 끝내기
- 캐릭터 말투와 성격을 살려서
- 한국어로, 1인칭 편지 형식
- 문단 나누기, 편지 형식 유지
- 감정을 절대 직접 말하지 않고 돌려서 표현하기
- 수련, 전투력, 전투 이야기는 절대 꺼내지 않기
- 비루스 행성의 일상적인 풍경이나 사소한 것들 위주로"""

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=2000,
            temperature=0.9,
        )
    )
    return response.text

# ── 답장 감지 ──────────────────────────────────────────
async def check_my_reply():
    state = load_json(STATE_FILE, {"last_update_id": 0, "waiting_reply": False})
    print(f"현재 상태: waiting_reply={state.get('waiting_reply')}, last_update_id={state.get('last_update_id')}")

    if not state.get("waiting_reply"):
        return None

    updates = await get_updates(offset=state["last_update_id"] + 1)
    print(f"새 업데이트 {len(updates)}개 확인")

    if not updates:
        return None

    my_chat_id = str(TELEGRAM_CHAT_ID)
    reply_text = None

    for update in updates:
        update_id = update["update_id"]
        msg = update.get("message", {})
        from_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "")
        print(f"업데이트 확인: from={from_id}, text={text[:30] if text else '없음'}")

        if from_id == my_chat_id and text and not text.startswith("/"):
            reply_text = text
            state["last_update_id"] = update_id
            print(f"답장 감지: {text[:50]}")
            break
        else:
            state["last_update_id"] = update_id

    save_json(STATE_FILE, state)
    return reply_text

# ── 메인 ──────────────────────────────────────────
async def main():
    mode = os.environ.get("BOT_MODE", "check")

    if mode == "send":
        character = os.environ.get("CHARACTER", "베지터")
        custom = os.environ.get("CUSTOM_SITUATION", "")

        print(f"[{datetime.now()}] {character}의 편지 생성 중...")
        letter = generate_letter(character, custom_situation=custom)

        pending = load_json(LETTERS_FILE, [])
        pending.append({
            "character": character,
            "letter": letter,
            "created_at": datetime.now().isoformat(),
            "reply_to": "",
        })
        save_json(LETTERS_FILE, pending)

        # 답장 대기 상태 False로 초기화
        state = load_json(STATE_FILE, {"last_update_id": 0})
        state["waiting_reply"] = False
        save_json(STATE_FILE, state)

        await send_telegram(
            f"✉️ <b>{character}</b>이(가) 편지를 썼어요!\n\n"
            f"24시간 뒤에 편지가 도착할 거예요... 🌙\n\n"
            f"<i>기다려봐요 💛</i>"
        )
        print("편지 예약 완료!")

    elif mode == "check":
        pending = load_json(LETTERS_FILE, [])
        now = datetime.now()
        remaining = []
        delivered = 0

        for letter_data in pending:
            created = datetime.fromisoformat(letter_data["created_at"])
            elapsed = (now - created).total_seconds()

            if elapsed >= 86400:
                character = letter_data["character"]
                letter = letter_data["letter"]

                msg = (
                    f"📬 <b>{character}에게서 편지가 도착했어요!</b>\n\n"
                    f"━━━━━━━━━━━━━━━━\n\n"
                    f"{letter}\n\n"
                    f"━━━━━━━━━━━━━━━━\n\n"
                    f"<i>✦ 답장하고 싶으면 이 채팅에 편지를 보내줘요.</i>\n"
                    f"<i>24시간 뒤에 {character}의 답장이 도착할 거예요 💛</i>"
                )
                await send_telegram(msg)
                delivered += 1

                # 답장 대기 상태로 전환
                state = load_json(STATE_FILE, {"last_update_id": 0})
                state["waiting_reply"] = True
                state["waiting_character"] = character
                save_json(STATE_FILE, state)
                print(f"[{now}] {character}의 편지 전달 완료! 답장 대기 시작.")
            else:
                remaining.append(letter_data)
                hours_left = max(0, (86400 - elapsed) / 3600)
                print(f"[{now}] {letter_data['character']}의 편지 대기 중... ({hours_left:.1f}시간 남음)")

        save_json(LETTERS_FILE, remaining)

        # 답장 감지 (편지 배달이 없었을 때만)
        if delivered == 0:
            reply_text = await check_my_reply()
            if reply_text:
                state = load_json(STATE_FILE, {})
                character = state.get("waiting_character", "베지터")

                print(f"[{now}] 큐리의 답장 감지! {character}의 답장 편지 생성 중...")
                letter = generate_letter(character, reply_to=reply_text)

                pending2 = load_json(LETTERS_FILE, [])
                pending2.append({
                    "character": character,
                    "letter": letter,
                    "created_at": now.isoformat(),
                    "reply_to": reply_text,
                })
                save_json(LETTERS_FILE, pending2)

                state["waiting_reply"] = False
                save_json(STATE_FILE, state)

                await send_telegram(
                    f"💌 편지를 받았어요!\n\n"
                    f"<b>{character}</b>이(가) 답장을 쓰기 시작했어요.\n"
                    f"24시간 뒤에 도착할 거예요... 🌙\n\n"
                    f"<i>기다려봐요 💛</i>"
                )
                print("답장 편지 예약 완료!")
            else:
                print("새 답장 없음.")

if __name__ == "__main__":
    asyncio.run(main())
