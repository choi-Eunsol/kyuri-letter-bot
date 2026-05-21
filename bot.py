import os
import json
import asyncio
import random
from datetime import datetime
import google.generativeai as genai
import httpx

# 환경변수
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Gemini 설정
genai.configure(api_key=GEMINI_API_KEY, transport='rest')
model = genai.GenerativeModel("gemini-3-flash-preview")

# 파일
LETTERS_FILE = "pending_letters.json"
STATE_FILE = "bot_state.json"
 
# ── 캐릭터 설정 ──────────────────────────────────────────
CHARACTERS = {
    "베지터": {
        "description": "사이어인의 왕자 베지터. 자존심 강하고 퉁명스럽지만 큐리를 깊이 아낀다. 편지엔 절대 감정을 직접 드러내지 않고 비꼬는 척 하면서 챙긴다. 큐리의 편지를 읽고 그에 대한 답장을 쓴다.",
        "sign": "— 베지터",
        "greeting": ["큐리에게", "불필요한 편지지만"],
    },
    "트랭크스": {
        "description": "베지터와 부르마의 아들 트랭크스. 큐리를 누나처럼 따르고 존경한다. 편지는 설레고 조금 어설프게 쓴다. 큐리 누나의 편지를 읽고 답장을 쓴다.",
        "sign": "— 트랭크스 올림",
        "greeting": ["큐리 누나에게", "누나, 저 트랭크스예요!"],
    },
    "피콜로": {
        "description": "과묵하고 냉정하지만 큐리를 묵묵히 지켜보는 피콜로. 편지는 매우 짧고 핵심만 담는다. 하지만 행간에 따뜻함이 배어있다.",
        "sign": "— 피콜로",
        "greeting": ["큐리에게", "별것 아닌 편지다"],
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
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        })
 
async def get_updates(offset: int = 0) -> list:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(url, params={"offset": offset, "limit": 10})
        data = res.json()
        return data.get("result", [])
 
# ── 편지 생성 ──────────────────────────────────────────
async def generate_letter(character: str, reply_to: str = "", custom_situation: str = "") -> str:
    char = CHARACTERS.get(character, CHARACTERS["베지터"])
    greeting = random.choice(char["greeting"])
    situation = custom_situation if custom_situation else SITUATION
 
    if reply_to:
        prompt = f"""
당신은 {character}입니다.
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
- 한국어로, 인터넷 감성 소설 문체로
- 편지 형식 유지 (문단 나누기)
- 감정을 직접 말하기보다 행동이나 상황으로 드러내기
"""
    else:
        prompt = f"""
당신은 {character}입니다.
캐릭터 설명: {char['description']}
 
{situation}
 
큐리에게 편지를 써주세요.
조건:
- 분량: 300자~600자 사이
- 인사말: "{greeting}" 으로 시작
- 마무리: "{char['sign']}" 으로 끝내기
- 캐릭터 말투와 성격을 살려서
- 한국어로, 인터넷 감성 소설 문체로
- 편지 형식 유지 (문단 나누기)
- 감정을 직접 말하기보다 행동이나 상황으로 드러내기
"""
 
    response = model.generate_content(
        prompt,
        request_options={"timeout": 120}
    )
    return response.text
 
# ── 새 메시지 확인 (내 답장 감지) ──────────────────────────────────────────
async def check_my_reply():
    state = load_json(STATE_FILE, {"last_update_id": 0, "waiting_reply": False})
 
    if not state.get("waiting_reply"):
        return None
 
    updates = await get_updates(offset=state["last_update_id"] + 1)
    if not updates:
        return None
 
    my_chat_id = str(TELEGRAM_CHAT_ID)
    reply_text = None
 
    for update in updates:
        update_id = update["update_id"]
        msg = update.get("message", {})
        from_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "")
 
        if from_id == my_chat_id and text and not text.startswith("/"):
            reply_text = text
            state["last_update_id"] = update_id
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
        letter = await generate_letter(character, custom_situation=custom)
 
        pending = load_json(LETTERS_FILE, [])
        pending.append({
            "character": character,
            "letter": letter,
            "created_at": datetime.now().isoformat(),
            "reply_to": "",
        })
        save_json(LETTERS_FILE, pending)
 
        state = load_json(STATE_FILE, {})
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
 
                state = load_json(STATE_FILE, {})
                state["waiting_reply"] = True
                state["waiting_character"] = character
                save_json(STATE_FILE, state)
 
                print(f"[{now}] {character}의 편지 전달 완료! 답장 대기 시작.")
            else:
                remaining.append(letter_data)
                hours_left = max(0, (86400 - elapsed) / 3600)
                print(f"[{now}] {letter_data['character']}의 편지 대기 중... ({hours_left:.1f}시간 남음)")
 
        save_json(LETTERS_FILE, remaining)
 
        if delivered == 0:
            reply_text = await check_my_reply()
            if reply_text:
                state = load_json(STATE_FILE, {})
                character = state.get("waiting_character", "베지터")
 
                print(f"[{now}] 큐리의 답장 감지! {character}의 답장 편지 생성 중...")
                letter = await generate_letter(character, reply_to=reply_text)
 
                pending = load_json(LETTERS_FILE, [])
                pending.append({
                    "character": character,
                    "letter": letter,
                    "created_at": now.isoformat(),
                    "reply_to": reply_text,
                })
                save_json(LETTERS_FILE, pending)
 
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
