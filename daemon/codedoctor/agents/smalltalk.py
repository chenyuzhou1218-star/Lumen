"""Small talk is answered, not investigated (2026-11-03).

"你好" used to start a whole investigation: a snapshot, the detail checklist, a scout sent out, the coupling graph
searched - tokens and minutes for a greeting. A message that is only a greeting, a thank-you, an acknowledgement or
"who are you / what can you do" is now marked at submit (body["chat"]) and goes to the model directly, without the
investigation around it. The model always answers, Claude Code and Codex too: there are no canned replies (the user's
rule, 2026-11-05, who could tell them by their speed). If it cannot answer, the user sees why.
"""

from __future__ import annotations

import re

# Whole messages, after lower-casing and dropping punctuation, spaces and trailing particles. A message is small talk
# when it is nothing but these (e.g. "你好你好", "hi, thanks").
GREET = ("你好", "您好", "你们好", "大家好", "嗨", "哈喽", "哈啰", "喂", "在吗", "在不在", "在么", "早", "早上好", "上午好",
         "中午好", "下午好", "晚上好", "hi there", "hello there", "hey there", "hi all", "hello everyone",
         "hi", "hello", "hey", "heya", "yo", "hiya", "goodmorning", "goodafternoon",
         "goodevening", "morning", "こんにちは", "こんばんは", "おはよう", "おはようございます", "안녕", "안녕하세요",
         "bonjour", "salut", "hola", "hallo", "guten tag", "ciao", "buongiorno", "olá", "ola", "oi", "привет",
         "здравствуйте")
THANKS = ("谢谢", "谢啦", "多谢", "感谢", "辛苦了", "thanks", "thank you", "thankyou", "thx", "ty", "bye", "再见", "拜拜",
          "晚安", "ありがとう", "ありがとうございます", "감사합니다", "고마워", "merci", "gracias", "danke", "grazie",
          "obrigado", "obrigada", "спасибо")
# In a conversation "好的" answers the last question ("shall I change it?") - a go-ahead, so work; alone, small talk.
ACK = ("好的", "好", "嗯", "嗯嗯", "行", "可以", "收到", "明白", "知道了", "ok", "okay", "cool", "great", "nice", "got it")
ABOUT = ("你是谁", "你叫什么", "你叫什么名字", "你能做什么", "你会什么", "你可以做什么", "你能干什么", "你会干什么",
         "介绍一下你自己", "介绍一下自己", "你是什么", "who are you", "what are you", "what can you do",
         "what do you do", "help", "帮助")
_DROP = re.compile(r"[\s\W_]+", re.UNICODE)
_TAIL = re.compile(r"[呀啊吖哈呢嘛啦哦喔噢~]+$")
MAX_CHARS = 40


def _norm(text: str) -> str:
    return _DROP.sub("", text.lower())


def _phrases(in_conversation: bool) -> list[str]:
    return sorted({_norm(p) for p in (*GREET, *THANKS, *ABOUT, *(() if in_conversation else ACK))}, key=len, reverse=True)


def is_smalltalk(text: str, in_conversation: bool = False) -> bool:
    """Only greetings, thanks, acknowledgements or "who are you" - nothing to investigate. In a conversation an
    acknowledgement ("好的") is a go-ahead and is not counted."""
    if not text or len(text.strip()) > MAX_CHARS or "\n" in text.strip():
        return False
    rest = _TAIL.sub("", _norm(text))
    if not rest:
        return False
    normed = _phrases(in_conversation)
    while rest:
        rest = _TAIL.sub("", rest)
        hit = next((p for p in normed if rest.startswith(p)), None)
        if hit is None:
            return bool(not rest)
        rest = rest[len(hit):]
    return True


SYSTEM = ("You are Lumen, an AI assistant on the user's computer, leading a small team. The user sent a short social message. "
          "Answer it the way you would in a conversation, in the user's language. Do not start any work.")
