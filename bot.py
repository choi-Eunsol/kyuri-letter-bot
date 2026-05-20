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

# 편지 설정 파일
LETTERS_FILE = "pending_letters.json"

# ── 설정 ──────────────────────────────────────────
# 여기서 캐릭터랑 상황 바꿔요!
CHARACTERS = {
    "베지터": {
        "description": "사이어인의 왕자 베지터. 자존심 강하고 퉁명스럽지만 큐리를 깊이 아낀다. 편지엔 절대 감정을 직접 드러내지 않고 비꼬는 척 하면서 챙긴다.",
        "sign": "— 베지터",
        "greeting": ["큐리에게", "불필요한 편지지만"],
    },
    "트랭크스": {
        "description": "베지터와 부르마의 아들 트랭크스. 큐리를 누나처럼 따르고 존경한다. 편지는 설레고 조금 어설프게 쓴다.",
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

# ── 편지 생성 ──────────────────────────────────────────
async def generate_letter(character: str, custom_situation: str = "") -> str:
    char = CHARACTERS.get(character, CHARACTERS["베지터"])
    greeting = random.choice(char["greeting"])
    situation = custom_situation if custom_situation else SITUATION

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
    response = model.generate_content(prompt)
    return response.text

# ── 텔레그램 메시지 전송 ──────────────────────────────────────────
async def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        })

# ── 대기 편지 저장/불러오기 ──────────────────────────────────────────
def load_pending() -> list:
    if not os.path.exists(LETTERS_FILE):
        return []
    with open(LETTERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_pending(letters: list):
    with open(LETTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(letters, f, ensure_ascii=False, indent=2)

# ── 메인 실행 ──────────────────────────────────────────
async def main():
    mode = os.environ.get("BOT_MODE", "check")

    if mode == "send":
        # 새 편지 생성 + 24시간 후 예약
        character = os.environ.get("CHARACTER", "베지터")
        custom = os.environ.get("CUSTOM_SITUATION", "")

        print(f"[{datetime.now()}] {character}의 편지 생성 중...")
        letter = await generate_letter(character, custom)

        # 예약 저장
        pending = load_pending()
        pending.append({
            "character": character,
            "letter": letter,
            "created_at": datetime.now().isoformat(),
        })
        save_pending(pending)

        await send_telegram(
            f"✉️ <b>{character}</b>이(가) 편지를 썼어요!\n\n"
            f"24시간 뒤에 편지가 도착할 거예요... 🌙\n\n"
            f"<i>기다려봐요 💛</i>"
        )
        print("편지 예약 완료!")

    elif mode == "check":
        # 24시간 지난 편지 전달
        pending = load_pending()
        now = datetime.now()
        remaining = []
        delivered = 0

        for letter_data in pending:
            created = datetime.fromisoformat(letter_data["created_at"])
            elapsed = (now - created).total_seconds()

            if elapsed >= 86400:  # 24시간 = 86400초
                character = letter_data["character"]
                letter = letter_data["letter"]

                msg = (
                    f"📬 <b>{character}에게서 편지가 도착했어요!</b>\n\n"
                    f"━━━━━━━━━━━━━━━━\n\n"
                    f"{letter}\n\n"
                    f"━━━━━━━━━━━━━━━━\n"
                    f"<i>✦ 편지를 소중히 간직하세요 ✦</i>"
                )
                await send_telegram(msg)
                delivered += 1
                print(f"[{now}] {character}의 편지 전달 완료!")
            else:
                remaining.append(letter_data)
                hours_left = max(0, (86400 - elapsed) / 3600)
                print(f"[{now}] {letter_data['character']}의 편지 대기 중... ({hours_left:.1f}시간 남음)")

        save_pending(remaining)

        if delivered == 0 and not remaining:
            print("대기 중인 편지 없음")

if __name__ == "__main__":
    asyncio.run(main())
