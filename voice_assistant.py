# voice_assistant.py  –  AI Voice + Text Assistant for EduPath

import os
import random
import streamlit as st
from live_data import counsellor_answer, _get_groq_client, fetch_edu_news

# ─────────────────────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────────────────────
CHAT_CSS = """
<style>
.user-bubble {
  background: linear-gradient(135deg,#667eea,#764ba2);
  color: white;
  border-radius: 18px 18px 4px 18px;
  padding: .8rem 1.1rem;
  margin-left: 15%;
  font-size: .92rem;
  line-height: 1.6;
  margin-bottom: .5rem;
}
.bot-bubble {
  background: #f4f2ff;
  color: #302b63;
  border: 1px solid #e0d9ff;
  border-radius: 18px 18px 18px 4px;
  padding: .8rem 1.1rem;
  margin-right: 15%;
  font-size: .92rem;
  line-height: 1.6;
  margin-bottom: .5rem;
}
.chat-label { font-size:.7rem; color:#888; margin-bottom:.2rem; }
.apply-btn {
  display:inline-block;
  background:linear-gradient(135deg,#667eea,#764ba2);
  color:white!important;
  padding:8px 20px;
  border-radius:30px;
  font-size:.85rem;
  font-weight:600;
  text-decoration:none;
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
#  VOICE RECORDER COMPONENT
#  Uses Web Speech API. On "Send to AI" it calls window.parent.postMessage
#  AND updates a visible textarea so users can confirm/edit before submitting.
# ─────────────────────────────────────────────────────────────────────────────
RECORDER_HTML = """<!DOCTYPE html>
<html>
<head>
<style>
  * { box-sizing:border-box; font-family:'Segoe UI',sans-serif; margin:0; padding:0; }
  body { background:transparent; padding:10px; }
  .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:8px; }
  button {
    padding:9px 20px; border:none; border-radius:22px;
    font-weight:700; cursor:pointer; font-size:13px; transition:all .2s;
  }
  #startBtn { background:linear-gradient(135deg,#11998e,#38ef7d); color:white; }
  #startBtn:hover { opacity:.85; }
  #stopBtn  { background:#ddd; color:#888; cursor:not-allowed; }
  #stopBtn.active { background:linear-gradient(135deg,#e65100,#f7971e); color:white; cursor:pointer; }
  #status   { font-size:12px; color:#555; }
  #transcript {
    background:#f4f2ff; border-radius:8px; padding:8px 12px;
    font-size:13px; color:#302b63; min-height:38px; margin-bottom:6px;
    border:1px solid #c5b9ff; width:100%;
  }
  #sendBtn {
    background:linear-gradient(135deg,#667eea,#764ba2);
    color:white; display:none; width:100%; margin-top:4px;
  }
  #sendBtn.show { display:block; }
  .hint { font-size:11px; color:#888; margin-top:4px; }
</style>
</head>
<body>
<div class="row">
  <button id="startBtn" onclick="startRec()">🎙 Start Speaking</button>
  <button id="stopBtn"  onclick="stopRec()">⏹ Stop</button>
  <span id="status">Idle – click Start and speak</span>
</div>
<div id="transcript">Your speech will appear here…</div>
<button id="sendBtn" onclick="sendToStreamlit()">✈️ Send to AI ↑</button>
<p class="hint">Tip: Works best in Chrome or Edge. After clicking Send, the text appears in the chat box below.</p>

<script>
let recog, finalText = "";

function startRec() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { alert("Use Chrome or Edge for speech recognition."); return; }
  recog = new SR();
  recog.lang = "en-IN";
  recog.interimResults = true;
  recog.continuous = false;
  finalText = "";
  document.getElementById("status").textContent = "🔴 Listening…";
  document.getElementById("startBtn").disabled = true;
  const sb = document.getElementById("stopBtn");
  sb.classList.add("active"); sb.disabled = false;
  document.getElementById("sendBtn").classList.remove("show");
  document.getElementById("transcript").textContent = "Listening…";

  recog.onresult = e => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) finalText += e.results[i][0].transcript + " ";
      else interim += e.results[i][0].transcript;
    }
    document.getElementById("transcript").textContent = (finalText + interim).trim() || "…";
  };

  recog.onend = () => {
    document.getElementById("status").textContent = finalText.trim()
      ? "✅ Speech captured – click Send to AI"
      : "❓ Nothing captured – try again";
    document.getElementById("startBtn").disabled = false;
    const sb = document.getElementById("stopBtn");
    sb.classList.remove("active"); sb.disabled = true;
    if (finalText.trim()) document.getElementById("sendBtn").classList.add("show");
  };

  recog.onerror = e => {
    document.getElementById("status").textContent = "Error: " + e.error;
    document.getElementById("startBtn").disabled = false;
  };
  recog.start();
}

function stopRec() { if (recog) recog.stop(); }

function sendToStreamlit() {
  const text = finalText.trim();
  if (!text) return;

  // ── Method 1: postMessage to parent listener ──
  window.parent.postMessage({ type: "VOICE_TRANSCRIPT", transcript: text }, "*");

  // ── Method 2: Attempt to fill the Streamlit text input directly ──
  const tryFill = (attempts) => {
    if (attempts <= 0) return;
    const input = (
      document.querySelector('input[aria-label="voice_bridge_input"]') ||
      window.parent.document.querySelector('input[aria-label="voice_bridge_input"]') ||
      Array.from(window.parent.document.querySelectorAll('input[type="text"]'))
           .find(el => el.placeholder && el.placeholder.includes("Type or speak"))
    );
    if (input) {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set
                  || Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, "value").set;
      setter.call(input, text);
      input.dispatchEvent(new Event("input",  { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      setTimeout(() => {
        input.dispatchEvent(new KeyboardEvent("keydown",  { key:"Enter", code:"Enter", keyCode:13, bubbles:true }));
        input.dispatchEvent(new KeyboardEvent("keypress", { key:"Enter", code:"Enter", keyCode:13, bubbles:true }));
        input.dispatchEvent(new KeyboardEvent("keyup",    { key:"Enter", code:"Enter", keyCode:13, bubbles:true }));
      }, 200);
    } else {
      setTimeout(() => tryFill(attempts - 1), 300);
    }
  };
  tryFill(5);

  document.getElementById("status").textContent = "✅ Sent to AI!";
  document.getElementById("sendBtn").classList.remove("show");
  document.getElementById("transcript").textContent = text;
  finalText = "";
}
</script>
</body>
</html>"""


# ── postMessage listener injected into the main Streamlit page ───────────────
# This catches the message from the recorder iframe and fills the text input.
LISTENER_JS = """
<script>
(function(){
  if (window._eduVoiceListener) return;
  window._eduVoiceListener = true;

  window.addEventListener("message", function(evt) {
    if (!evt.data || evt.data.type !== "VOICE_TRANSCRIPT") return;
    const transcript = evt.data.transcript;
    if (!transcript) return;

    const fillInput = (retries) => {
      if (retries <= 0) return;
      // Find the voice bridge text input
      let inp = document.querySelector('input[aria-label="voice_bridge_input"]');
      if (!inp) {
        inp = Array.from(document.querySelectorAll('[data-testid="stTextInput"] input'))
                   .find(el => el.placeholder && el.placeholder.includes("Type or speak"));
      }
      if (inp) {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        setter.call(inp, transcript);
        inp.dispatchEvent(new Event("input",  { bubbles: true }));
        inp.dispatchEvent(new Event("change", { bubbles: true }));
        setTimeout(() => {
          inp.dispatchEvent(new KeyboardEvent("keydown",  { key:"Enter", code:"Enter", keyCode:13, bubbles:true, cancelable:true }));
          inp.dispatchEvent(new KeyboardEvent("keypress", { key:"Enter", code:"Enter", keyCode:13, bubbles:true, cancelable:true }));
          inp.dispatchEvent(new KeyboardEvent("keyup",    { key:"Enter", code:"Enter", keyCode:13, bubbles:true, cancelable:true }));
        }, 200);
      } else {
        setTimeout(() => fillInput(retries - 1), 400);
      }
    };
    fillInput(8);
  });
})();
</script>
"""

# ── Browser TTS (no gTTS required) ──────────────────────────────────────────
def _speak_tts(text: str):
    """Use st.components.v1.html to speak text via browser speechSynthesis."""
    # Clean markdown formatting for speech
    clean = text[:3000]
    clean = clean.replace("**", "").replace("*", "").replace("#", "")
    clean = clean.replace("`", "").replace("\n", ". ").replace("  ", " ")
    # Escape for JS string
    safe = clean.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
    html = f"""<!DOCTYPE html><html><head></head><body>
<script>
(function(){{
  // Try parent window first (main browser context), fallback to own window
  var synth = (window.parent && window.parent.speechSynthesis) || window.speechSynthesis;
  if(!synth) return;
  synth.cancel();
  var text = '{safe}';
  var chunks = [];
  var remaining = text;
  while(remaining.length > 0) {{
    var end = Math.min(remaining.length, 200);
    if(end < remaining.length) {{
      var lastDot = remaining.lastIndexOf('.', end);
      if(lastDot > 50) end = lastDot + 1;
    }}
    chunks.push(remaining.substring(0, end));
    remaining = remaining.substring(end);
  }}
  var i = 0;
  function speakNext() {{
    if(i >= chunks.length) return;
    var utt = new SpeechSynthesisUtterance(chunks[i]);
    utt.lang = 'en-IN';
    utt.rate = 0.95;
    utt.pitch = 1.0;
    utt.onend = function() {{ i++; speakNext(); }};
    synth.speak(utt);
  }}
  speakNext();
}})();
</script>
</body></html>"""
    st.components.v1.html(html, height=0, scrolling=False)

def _stop_tts():
    """Stop any ongoing TTS speech."""
    html = """<!DOCTYPE html><html><head></head><body>
<script>
(function(){
  var synth = (window.parent && window.parent.speechSynthesis) || window.speechSynthesis;
  if(synth) synth.cancel();
})();
</script>
</body></html>"""
    st.components.v1.html(html, height=0, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PAGE RENDERER
# ─────────────────────────────────────────────────────────────────────────────
def render_assistant_page(groq_ok: bool = True):
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0f0c29,#302b63);
                border-radius:20px;padding:1.5rem 2rem;margin-bottom:1.5rem;">
      <h1 style="font-family:'Sora',sans-serif;color:white;margin:0;font-size:1.8rem;">
        💬 EduPath AI – Voice + Text Counsellor
      </h1>
      <p style="color:#e0d9ff;margin:.5rem 0 0;">
        Powered by DuckDuckGo live search + Groq Llama 3.3 · Speak or type your question
      </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(CHAT_CSS, unsafe_allow_html=True)

    # Inject postMessage listener into main page
    st.markdown(LISTENER_JS, unsafe_allow_html=True)

    if not groq_ok:
        st.warning(
            "⚠️ **AI Engine Offline** – Groq API key missing or invalid.\n\n"
            "Add your key to `.streamlit/secrets.toml`:\n```\nGROQ_API_KEY = \"gsk_...\"\n```\n"
            "Get a free key at https://console.groq.com"
        )

    # ── Session state ──────────────────────────────────────────────────────
    for k, v in [("chat_messages",[]), ("chat_pending",None),
                 ("voice_enabled",False), ("tts_enabled",False),
                 ("tts_pending",None)]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Toggles ───────────────────────────────────────────────────────────
    col_v1, col_v2, col_v3, col_v4 = st.columns(4)
    with col_v1:
        voice_on = st.toggle("🎙 Voice Input", value=st.session_state.voice_enabled, key="voice_toggle")
        st.session_state.voice_enabled = voice_on
    with col_v2:
        tts_on = st.toggle("🔊 Read Answers Aloud", value=st.session_state.tts_enabled, key="tts_toggle")
        st.session_state.tts_enabled = tts_on
    with col_v3:
        # Manual read button for last answer
        if st.session_state.chat_messages:
            if st.button("🔊 Read Last Answer", key="read_last_btn", width="stretch"):
                # Find last bot message
                for msg in reversed(st.session_state.chat_messages):
                    if msg["role"] == "assistant" and not msg["content"].startswith("⚠️"):
                        st.session_state.tts_pending = msg["content"]
                        break
    with col_v4:
        # Stop speaking button
        if st.button("🔇 Stop Speaking", key="stop_tts_btn", width="stretch"):
            st.session_state.tts_pending = None
            _stop_tts()

    # ── Fire pending TTS (survives rerun) ─────────────────────────────────
    if st.session_state.tts_pending:
        tts_text = st.session_state.tts_pending
        st.session_state.tts_pending = None
        _speak_tts(tts_text)

    # ── Quick question chips ───────────────────────────────────────────────
    suggestions = [
        # Universities & Rankings
        "What exams do I need for MS in CS in USA?",
        "Best free-tuition universities in Germany?",
        "Top 10 universities for Data Science worldwide?",
        "Cheapest countries with good QS rankings?",
        "Best universities in Canada for MBA?",
        "Top universities in Australia for Engineering?",
        "Which UK universities accept 60% GPA?",
        "Best colleges for AI and Machine Learning?",
        # Exams
        "GRE vs GMAT – which for MBA?",
        "GATE score required for IIT M.Tech 2026?",
        "IELTS score for University of Toronto?",
        "TOEFL vs IELTS – which is easier?",
        "SAT score needed for Ivy League?",
        "PTE Academic vs IELTS – acceptance?",
        # Scholarships & Funding
        "How to apply for Chevening Scholarship?",
        "Fulbright scholarship eligibility for Indians?",
        "Full-ride scholarships in USA for Masters?",
        "DAAD scholarship for Germany – how to apply?",
        "Erasmus Mundus scholarship deadlines?",
        # Visa & Immigration
        "Canada PR pathway after Masters?",
        "USA OPT rules for STEM students?",
        "UK Graduate Route visa – how to apply?",
        "Australia post-study work visa duration?",
        # Loans & Finances
        "Best education loan for studying abroad?",
        "SBI vs HDFC education loan comparison?",
        "How much bank balance needed for USA F-1 visa?",
        # Career & SOP
        "How to write a strong SOP for MS in CS?",
        "Best countries for post-study work opportunities?",
        "Average salary after MS in USA?",
        "ROI of studying MBA abroad vs India?",
    ]
    # Shuffle and pick a few suggestions for each page load
    if "shuffled_suggestions" not in st.session_state:
        shuffled = list(suggestions)
        random.shuffle(shuffled)
        st.session_state.shuffled_suggestions = shuffled[:8]

    shown = st.session_state.shuffled_suggestions
    st.markdown("#### 💡 Quick Questions")
    cols = st.columns(4)
    for i, q in enumerate(shown):
        with cols[i % 4]:
            if st.button(q, key=f"chip_{i}", width="stretch"):
                st.session_state.chat_pending = q
                # Reshuffle on next question pick
                del st.session_state["shuffled_suggestions"]
                st.rerun()

    st.markdown("---")

    # ── Voice recorder ────────────────────────────────────────────────────
    if voice_on:
        st.markdown("""
        <div style="background:#e8f5e9;border-radius:12px;padding:.8rem 1.2rem;
                    border-left:4px solid #11998e;margin-bottom:1rem;">
          <b style="color:#2e7d32;">🎙 Voice Mode Active</b>
          <span style="font-size:.84rem;color:#555;margin-left:8px;">
            Click Start → speak → Stop → Send to AI
          </span>
        </div>
        """, unsafe_allow_html=True)
        st.components.v1.html(RECORDER_HTML, height=170, scrolling=False)

    # ── Chat history ──────────────────────────────────────────────────────
    chat_area = st.container()
    with chat_area:
        for msg in st.session_state.chat_messages:
            if msg["role"] == "user":
                st.markdown(
                    f'<div style="text-align:right;margin-bottom:8px;">'
                    f'<div class="chat-label">You</div>'
                    f'<div class="user-bubble">{msg["content"]}</div></div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div style="margin-bottom:8px;">'
                    f'<div class="chat-label">🤖 EduPath AI</div>'
                    f'<div class="bot-bubble">{msg["content"]}</div></div>',
                    unsafe_allow_html=True
                )

    # ── Input row ────────────────────────────────────────────────────────
    inp_col, btn_col = st.columns([5, 1])
    with inp_col:
        user_input = st.text_input(
            "voice_bridge_input",
            placeholder="Type or speak your question…",
            label_visibility="collapsed",
            key="chat_text_input",
        )
    with btn_col:
        send_btn = st.button("Send ✈️", width="stretch", key="send_btn_real")

    # ── Submission logic ──────────────────────────────────────────────────
    last_processed = st.session_state.get("_last_input", "")
    if send_btn and user_input.strip():
        st.session_state.chat_pending = user_input.strip()
        st.session_state["_last_input"] = user_input.strip()
        st.rerun()
    elif user_input.strip() and user_input.strip() != last_processed:
        st.session_state.chat_pending = user_input.strip()
        st.session_state["_last_input"] = user_input.strip()
        st.rerun()

    # ── Process pending ───────────────────────────────────────────────────
    if st.session_state.chat_pending:
        pending = st.session_state.chat_pending
        st.session_state.chat_pending = None
        st.session_state.chat_messages.append({"role": "user", "content": pending})

        with st.spinner("🤖 EduPath AI is thinking…"):
            try:
                stream = counsellor_answer(pending, st.session_state.chat_messages, stream=True)
                full_response = ""

                if isinstance(stream, str):
                    full_response = stream
                    st.markdown(
                        f'<div class="bot-bubble">🤖 {full_response}</div>',
                        unsafe_allow_html=True
                    )
                else:
                    placeholder = st.empty()
                    for chunk in stream:
                        if hasattr(chunk, "choices") and chunk.choices:
                            delta = chunk.choices[0].delta.content
                            if delta:
                                full_response += delta
                                placeholder.markdown(
                                    f'<div class="bot-bubble">🤖 {full_response}▌</div>',
                                    unsafe_allow_html=True
                                )
                    placeholder.markdown(
                        f'<div class="bot-bubble">🤖 {full_response}</div>',
                        unsafe_allow_html=True
                    )

            except Exception as e:
                full_response = f"⚠️ AI Error: {e}"

        st.session_state.chat_messages.append({"role": "assistant", "content": full_response})

        # Browser TTS – store in session state so it fires AFTER rerun
        if st.session_state.tts_enabled and full_response and not full_response.startswith("⚠️"):
            st.session_state.tts_pending = full_response

        st.rerun()

    # ── Clear button ─────────────────────────────────────────────────────
    if st.session_state.chat_messages:
        if st.button("🗑️ Clear Chat History", key="clear_chat"):
            st.session_state.chat_messages = []
            st.session_state["_last_input"] = ""
            st.rerun()