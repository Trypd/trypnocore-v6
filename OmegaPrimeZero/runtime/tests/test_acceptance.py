"""Acceptance checks from the build doc, plus the self-voice filter."""
from __future__ import annotations

import io
import json
import wave
from pathlib import Path

import pytest

from runtime.body.agent_zero import tool_context
from runtime.dream.deep import deep_sleep
from runtime.dream.light import Candidate, light_sleep
from runtime.dream.rem import rem
from runtime.harness.cortex_pin import Actor, pin
from runtime.kanban.board import Board
from runtime.memory import Hole, MemoryDouble, OmegaClawWriter, Proof
from runtime.mind.boot import END, START, inject, load_boot, outside_markers
from runtime.mind.fake_mind import fake_mind
from runtime.mind.loader import prepare_mind
from runtime.mind.schema import SchemaError, assert_content_only, parse_assistant_content, utterance_of
from runtime.mind.turn import Tape, build_frame, run_turn
from runtime.night.reward import load_night_config, score
from runtime.chat import completion_body, server_command
from runtime.live_prompt import choose_memories, explicit_notes, live_sections, reconcile
from runtime.memory.metta_space import MettaSpace
from runtime.one_turn import TEMPERATURE, TurnError, continue_turn, fold_to_content, prompt_for
from runtime.paths import LLAMA_SERVER
from runtime.senses import collect_voice, sense_command, sense_messages, write_tone
from runtime.paths import AUDIO_STACK, MIND_GGUF, MIND_ID, VL_GGUF
from runtime.planfiles import ToolSession
from runtime.refine.refine import apply_patch, rollback, snapshot
from runtime.skills.gepa import GepaReject, review_candidate
from runtime.slaves.audio import heard_line, speak
from runtime.slaves.self_voice import SelfVoiceBuffer
from runtime.slaves.vl import saw_line, slave_prompt
from runtime.trinkets.composer import compose
from runtime.trinkets.forage_trinket import ForageTrinket
from runtime.trinkets.proactive_memory_trinket import ProactiveMemoryTrinket


BOOT = f"HEAD\n{START}\nold lens\n{END}\nTAIL\n"


def test_llama_banner_is_not_the_reply():
    raw = "Loading model...\nbuild : b11146\n> hello\nthink: listening\n\nHello.\nExiting...\n"
    folded = fold_to_content(raw)
    assert "Loading model" not in folded
    assert "b11146" not in folded
    parsed = parse_assistant_content(folded)
    assert parsed.utterance == "Hello."
    messy = fold_to_content(
        "Say who you are. think: one short line\nthink: I looked. Hello there."
    )
    parsed = parse_assistant_content(messy)
    assert parsed.think_lines == ("think: I looked.",)
    assert parsed.utterance == "Hello there."


def test_think_tags_fold_into_content():
    folded = fold_to_content("<think>\nlook at the note\n</think>\n\nThe note is open.")
    parsed = parse_assistant_content(folded)
    assert parsed.think_lines == ("think: look at the note",)
    assert parsed.utterance == "The note is open."
    assert "reasoning" not in folded


def test_temperature_is_pinned_and_senses_stay_turn_based():
    assert TEMPERATURE == 1.1
    command = sense_command(
        cli=Path("llama-omni-cli"),
        prefix="case_",
        ref_audio=Path("ref.wav"),
    )
    assert "--temp" in command
    assert command[command.index("--temp") + 1] == "1.1"
    assert "--omni" in command
    assert "--test" in command
    assert "llama-omni-server" not in command
    assert "--duplex" not in command
    assert "AGENTS.md" not in " ".join(command)
    saw, heard, content, buffer = sense_messages("The frame is green.", b"tone-bytes", b"voice-bytes")
    assert saw == "saw: one green frame"
    assert heard == "heard: a short tone"
    assert parse_assistant_content(content).utterance == "The frame is green."
    assert buffer.is_self(b"voice-bytes", "The frame is green.")
    assert "reasoning" not in content


def test_chat_keeps_one_loaded_mind():
    assert LLAMA_SERVER.is_file()
    command = server_command()
    joined = " ".join(command)
    assert command[command.index("--temp") + 1] == "1.1"
    assert "--no-webui" in command
    assert command[command.index("--reasoning") + 1] == "off"
    assert "llama-omni-server" not in joined
    assert "--duplex" not in joined
    body = completion_body([{"role": "user", "content": "Hello."}])
    assert body["temperature"] == 1.1
    assert body["stream"] is False
    assert body["messages"][0]["role"] == "system"
    assert "think:" in body["messages"][0]["content"]
    assert "I Analogue" in body["messages"][0]["content"]
    assert body["messages"][-1] == {"role": "user", "content": "Hello."}
    assert body["messages"][-2]["content"].startswith("[boot]\n")
    assert body["messages"][-2]["content"].count("[boot]") == 1
    assert "stateless token generator" in body["messages"][-2]["content"]
    stale = completion_body([
        {"role": "user", "content": "[boot]\nold copy"},
        {"role": "user", "content": "Hello."},
    ])
    assert "[boot]\nold copy" not in [message["content"] for message in stale["messages"]]
    assert sum(message["content"].startswith("[boot]\n") for message in stale["messages"]) == 1


def test_voice_chunks_join_in_numeric_order(tmp_path: Path):
    write_tone(tmp_path / "wav_10.wav", seconds=0.05)
    write_tone(tmp_path / "wav_2.wav", seconds=0.05)
    blob = collect_voice(tmp_path)
    assert blob is not None
    with wave.open(io.BytesIO(blob), "rb") as handle:
        assert handle.getnframes() == 1600


def test_second_turn_keeps_the_first_reply(tmp_path: Path):
    first_assistant = (
        "think: I am a self-reflective recursive agent, generating immediate responses.\n"
        "\n"
        "I am a standing wave."
    )
    tape_path = tmp_path / "one-turn.json"
    tape_path.write_text(
        json.dumps({
            "messages": [
                {"role": "user", "content": "Say who you are in one sentence."},
                {"role": "assistant", "content": first_assistant},
            ]
        }),
        encoding="utf-8",
    )
    seen: dict = {}

    def fake_generate(said: str, history=None, **_kwargs) -> str:
        seen["said"] = said
        seen["history"] = history
        return "think: I read the last think line.\n\nI am a self-reflective recursive agent, generating immediate responses."

    stored = continue_turn("Repeat the think line.", tape_path=tape_path, generate_fn=fake_generate)
    payload = json.loads(tape_path.read_text(encoding="utf-8"))
    assert len(payload["messages"]) == 4
    assert payload["messages"][1]["content"] == first_assistant
    assert payload["messages"][2]["role"] == "user"
    assert "Repeat the think line." in payload["messages"][2]["content"]
    assert "reasoning" not in payload["messages"][3]
    assert parse_assistant_content(stored).utterance.startswith("I am a self-reflective recursive agent")
    assert seen["history"][1]["content"] == first_assistant
    quoted = prompt_for("Repeat the think line.", seen["history"])
    assert "self-reflective recursive agent" in quoted
    assert quoted.endswith("Then one spoken sentence.")
    assert prompt_for("Hello.") == "Hello.\n\nReply in this exact shape and nothing else.\nthink: one short line about what you are doing\n\nThen one spoken sentence."
    with pytest.raises(TurnError):
        continue_turn("Again.", tape_path=tmp_path / "missing.json", generate_fn=fake_generate)


def test_think_lines_survive_into_the_next_request():
    tape = Tape()
    content = run_turn(tape, fake_mind, [])
    nxt = tape.request()
    blob = "\n".join(message["content"] for message in nxt)
    for line in parse_assistant_content(content).think_lines:
        assert line in blob
    assert "reasoning" not in nxt[-1]
    with pytest.raises(SchemaError):
        assert_content_only({"role": "assistant", "content": content, "reasoning": "hidden"})


def test_image_without_audio_speaks_and_does_not_hear():
    saw = saw_line("a red margin note")
    heard = heard_line(None, None, SelfVoiceBuffer())
    assert saw == "saw: a red margin note"
    assert heard is None
    spoken = speak(utterance_of(fake_mind([])), SelfVoiceBuffer())
    assert spoken["text"] == "The note says the workspace is the broadcast, not the store."


def test_audio_body_is_the_utterance_and_self_voice_is_dropped():
    buffer = SelfVoiceBuffer()
    utterance = "The note says the workspace is the broadcast, not the store."
    spoken = speak(utterance, buffer)
    assert spoken["text"] == utterance
    assert heard_line(spoken["waveform"], utterance, buffer) is None
    assert heard_line(b"someone-else", "a different clause", buffer) == "heard: a different clause"


def test_slaves_and_tools_do_not_receive_the_boot():
    assert slave_prompt("pixels", BOOT) == "pixels"
    with pytest.raises(RuntimeError):
        slave_prompt(BOOT, BOOT)
    ctx = tool_context("click the margin")
    assert ctx["boot"] == ""
    assert ctx["answers_as_person"] is False


def test_rem_writes_first_person_and_deep_sleep_is_the_atom_gate(tmp_path: Path):
    store = MemoryDouble()
    stretch = [
        Candidate("I held the note open on 2026-09-10.", "think-1", 2, "think", "the note"),
        Candidate("I held the note open on 2026-09-10.", "think-1", 2, "think", "the note"),
        Candidate("saw: a red margin", None, 9, "saw", "pixels"),
    ]
    before = store.count()
    staged = light_sleep(stretch)
    assert store.count() == before
    dreams = tmp_path / "DREAMS.md"
    materialized = rem(staged, dreams)
    assert "I held the note open on 2026-09-10." in dreams.read_text(encoding="utf-8")
    assert "The assistant" not in dreams.read_text(encoding="utf-8")
    assert store.count() == before
    promoted = deep_sleep(materialized, store)
    assert store.count() == 1
    assert len(promoted) == 1
    with pytest.raises(Exception):
        store.phase = "awake"
        store.assert_atom(Proof("saw: a red margin", "pixels", "no"))


def test_trinket_empty_and_proactive_without_search():
    ctx = {"memories": ["atom fact/stm-is-not-ltm"], "search_calls": 0}
    sections = compose([ForageTrinket(), ProactiveMemoryTrinket()], ctx)
    assert sections[0] == ""
    assert "atom fact/stm-is-not-ltm" in sections[1]
    assert ctx["search_calls"] == 0
    frame = build_frame(boot="boot", supplemental="", tape=Tape(), trinket_sections=sections, sensory=[])
    assert any("stm-is-not-ltm" in message["content"] for message in frame)


def test_plan_files_exist_before_the_third_call_and_stay_off_the_tape(tmp_path: Path):
    session = ToolSession(tmp_path, expected_tool_calls=6)
    session.call()
    session.call()
    session.call()
    for name in ("task_plan.md", "findings.md", "progress.md"):
        assert (tmp_path / name).is_file()
    tape = Tape()
    tape.append("user", "hello")
    blob = "\n".join(message["content"] for message in tape.request())
    assert "task_plan" not in blob


def test_inject_changes_only_the_marker_interior(tmp_path: Path):
    path = tmp_path / "BOOT.md"
    path.write_text(BOOT, encoding="utf-8")
    before = load_boot(path)
    inject(path, "new lens")
    after = path.read_text(encoding="utf-8")
    assert outside_markers(before) == outside_markers(after)
    assert "new lens" in after
    assert "old lens" not in after


def test_gepa_rejects_the_bad_candidates():
    ok = dict(purpose_before="same", purpose_after="same", tests_pass=True, tool_descriptions=["short"], mid_conversation=False)
    review_candidate(text="fine", **ok)
    with pytest.raises(GepaReject):
        review_candidate(text="x" * (15 * 1024 + 1), **ok)
    with pytest.raises(GepaReject):
        review_candidate(text="fine", purpose_before="same", purpose_after="other", tests_pass=True, tool_descriptions=["short"], mid_conversation=False)
    with pytest.raises(GepaReject):
        review_candidate(text="fine", purpose_before="same", purpose_after="same", tests_pass=False, tool_descriptions=["short"], mid_conversation=False)


def test_refine_rejects_the_boot_and_rolls_back(tmp_path: Path):
    supplement = tmp_path / "supplement.txt"
    boot = tmp_path / "BOOT.md"
    supplement.write_text("base\n", encoding="utf-8")
    boot.write_text(BOOT, encoding="utf-8")
    snap = snapshot(supplement)
    boot_before = boot.read_bytes()
    with pytest.raises(Exception):
        apply_patch(supplement, boot, START + "no")
    assert boot.read_bytes() == boot_before
    apply_patch(supplement, boot, "extra line\n")
    assert supplement.read_text(encoding="utf-8") != snap.decode()
    rollback(supplement, snap)
    assert supplement.read_bytes() == snap


def test_night_config_trains_only_the_8b_and_missing_atoms_cost():
    cfg = load_night_config(Path(__file__).resolve().parents[1] / "night" / "rl.toml")
    assert cfg["trainable"] == MIND_ID
    store = MemoryDouble()
    assert score({"cited_atoms": ["missing"], "audio_text": "a", "utterance": "a"}, store) < 0
    store.remember(Proof("the note", "think-1", "I held it"))
    assert score({"cited_atoms": ["think-1"], "audio_text": "a", "utterance": "a", "plan_present": True}, store) > 0


def test_one_executive_and_no_worker_mind(tmp_path: Path):
    mind = Actor("mind", MIND_ID, can_think=True)
    slave = Actor("vl", "LFM2.5-VL-3B-heretic", can_think=False)
    assert pin([mind, slave]) is mind
    with pytest.raises(Exception):
        pin([mind, Actor("other", MIND_ID, can_think=True)])
    board = Board(tmp_path / "kanban.db")
    board.add_card("read the note")
    with pytest.raises(Exception):
        board.spawn_worker()
    board.close()


def test_checkpoints_are_pinned_and_weights_are_not_read(tmp_path: Path):
    boot = tmp_path / "BOOT.md"
    boot.write_text(BOOT, encoding="utf-8")
    prepare_mind(boot, train=False)
    assert MIND_GGUF.is_file() and VL_GGUF.is_file()
    assert all(path.is_file() for path in AUDIO_STACK)
    assert len(AUDIO_STACK) == 5
    assert MIND_GGUF.stat().st_size > 1_000_000
    assert all(path.stat().st_size > 1_000_000 for path in AUDIO_STACK)
    with pytest.raises(Exception):
        prepare_mind(boot, train=True)


def test_failed_query_is_a_hole_and_production_writer_refuses():
    store = MemoryDouble()
    with pytest.raises(Hole):
        store.query("(match $x)")
    with pytest.raises(Exception):
        OmegaClawWriter().assert_atom(Proof("x", "y", "z"))


def test_trinket_suffix_leaves_the_system_prefix_stable():
    plain = completion_body([{"role": "user", "content": "Hello."}])
    first_mark = "[trinket time]\n2026-09-29T00:00:00+00:00"
    marked = completion_body(
        [{"role": "user", "content": "Hello."}],
        trinket_sections=[first_mark],
    )
    assert plain["messages"][0] == marked["messages"][0]
    assert marked["messages"][-1] == {"role": "user", "content": "Hello."}
    assert marked["messages"][-2]["content"].startswith("[boot]\n")
    assert first_mark in [message["content"] for message in marked["messages"]]
    frozen = [
        message for message in marked["messages"][1:]
        if not message["content"].startswith("[boot]\n")
    ]
    frozen.append({"role": "assistant", "content": "think: ok\n\nHi."})
    frozen.append({"role": "user", "content": "Again."})
    second_mark = "[trinket time]\n2026-09-29T00:00:01+00:00"
    second = completion_body(frozen, trinket_sections=[second_mark])
    assert second["messages"][0] == plain["messages"][0]
    contents = [message["content"] for message in second["messages"]]
    assert first_mark in contents
    assert contents[-1] == "Again."
    assert contents[-2].startswith("[boot]\n")
    assert contents[-3] == second_mark
    assert sum(content.startswith("[boot]\n") for content in contents) == 1
    saved = [
        {"role": "user", "content": first_mark},
        {"role": "user", "content": "Hello."},
        {"role": "assistant", "content": "think: ok\n\nHi."},
    ]
    client = [
        {"role": "user", "content": "Hello."},
        {"role": "assistant", "content": "think: ok\n\nHi."},
        {"role": "user", "content": "Again."},
    ]
    merged = reconcile(client, saved)
    assert merged[0]["content"] == first_mark
    assert merged[-1]["content"] == "Again."


def test_metta_remember_reloads_and_default_writer_refuses(tmp_path: Path):
    space = MettaSpace(tmp_path / "atoms.metta")
    with pytest.raises(Exception):
        OmegaClawWriter().assert_atom(Proof("x", "y", "z"))
    with pytest.raises(Exception):
        OmegaClawWriter().remember(Proof("x", "y", "z"))
    with pytest.raises(Exception):
        space.assert_atom(Proof("awake write", "p", "e"))
    assert explicit_notes("hello there") == []
    assert explicit_notes("remember saw: a cat") == []
    note = explicit_notes("remember that the gate is shut")[0]
    assert note.claim == "the gate is shut"
    reminder = explicit_notes("remind me to check the gate")[0]
    assert reminder.claim == "reminder: check the gate"
    writer = OmegaClawWriter(space)
    writer.remember(note)
    writer.remember(note)
    writer.remember(reminder)
    with pytest.raises(Exception):
        writer.remember(Proof("saw: a cat", "pixels", "no"))
    reloaded = MettaSpace(tmp_path / "atoms.metta")
    assert reloaded.claims() == ["the gate is shut", "reminder: check the gate"]
    assert reloaded.count() == 2
    with pytest.raises(Hole):
        reloaded.query("((((")


    assert choose_memories(reloaded.claims(), "is the gate shut") == ["the gate is shut"]
    sections = live_sections(
        {
            "now": "2026-09-29T00:00:00+00:00",
            "memories": ["the gate is shut"],
            "reminders": ["check the gate"],
            "curator_status": "metta atoms: 2",
            "lora_loaded": False,
            "channels": {},
        }
    )
    joined = "\n".join(sections)
    assert "[trinket time]\n2026-09-29T00:00:00+00:00" in joined
    assert "the gate is shut" in joined
    assert "check the gate" in joined
    assert "metta atoms: 2" in joined
    assert "not loaded" in joined
    assert "yesterday" not in joined.lower()
    text = (tmp_path / "atoms.metta").read_text(encoding="utf-8")
    assert text.startswith("(memory ")


def test_metta_prunes_oldest_beyond_max_atoms(tmp_path: Path):
    from runtime.memory.metta_space import MAX_ATOMS

    space = MettaSpace(tmp_path / "atoms.metta")
    for index in range(MAX_ATOMS + 25):
        space.remember(Proof(f"claim number {index}", f"ptr{index:04d}", f"ev {index}"))
    assert space.count() == MAX_ATOMS
    claims = space.claims()
    assert claims[0] == "claim number 25"
    assert claims[-1] == f"claim number {MAX_ATOMS + 24}"
    reloaded = MettaSpace(tmp_path / "atoms.metta")
    assert reloaded.count() == MAX_ATOMS


def test_runtime_source_does_not_import_a_second_mind():
    root = Path(__file__).resolve().parents[1]
    banned = ("ctm_ai", "ctm-ai", "spawn_agent", "QuantumClaw", "qclaw")
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in banned:
            assert needle not in text, f"{needle} in {path}"


def test_memory_api_round_trip(tmp_path, monkeypatch):
    from starlette.testclient import TestClient
    import runtime.chat as chat

    monkeypatch.setattr(chat, "METTA_PATH", tmp_path / "atoms.metta")
    monkeypatch.setattr(chat, "_store", None)
    client = TestClient(chat.app)
    assert client.get("/memory/atoms").status_code == 200
    reply = client.post("/memory/remember", json={"line": "remember that the gate is shut"})
    assert reply.status_code == 200
    assert reply.json()["remembered"] == 1
    atoms = client.get("/memory/atoms").json()["atoms"]
    assert "the gate is shut" in atoms
    context = client.get("/memory/context", params={"line": "is the gate shut?"})
    assert context.status_code == 200
    assert any("the gate is shut" in section for section in context.json()["sections"])
    empty = client.post("/memory/remember", json={"line": ""})
    assert empty.status_code == 400


def test_memory_extract_first_person_gate(tmp_path):
    from runtime.memory.extract import harvest_reply
    from runtime.memory.metta_space import MettaSpace

    store = MettaSpace(tmp_path / "atoms.metta")
    third_person = "think: the user is asking about the gate again\n\nThe gate stands open."
    assert harvest_reply(third_person, "2026-10-04T00:00:00", store) == 0
    first_person = "think: I notice the gate is shut and I hold that fact\n\nThe gate stands."
    assert harvest_reply(first_person, "2026-10-04T00:00:01", store) == 1
    assert "I notice the gate is shut and I hold that fact" in store.claims()
    # A reply with no parseable think block yields nothing, no crash.
    assert harvest_reply("just text", "2026-10-04T00:00:02", store) == 0
    # The Jaynesian block form: bare "think:" line, spatialized lines follow.
    block_form = (
        "think:\nSpatial orientation: I am turning to face the new memory system\n"
        "Metacognitive monitoring: I feel the old tape slipping away\n\nI am here."
    )
    assert harvest_reply(block_form, "2026-10-04T00:00:03", store) == 2
    # In block form the first-person gate is the discriminator: one anchored
    # line promotes, the unanchored one does not.
    mixed = "think:\nI hold this line\nrandom unanchored thought\n\nAnswer."
    assert harvest_reply(mixed, "2026-10-04T00:00:04", store) == 1


def test_memory_pool_is_identity_slaver(tmp_path):
    from runtime.memory import Proof
    from runtime.memory.metta_space import MettaSpace, check_pool

    jem = MettaSpace.for_pool(tmp_path, "Jem-Stein")  # case folds
    budnik = MettaSpace.for_pool(tmp_path, "budnik")
    jem.remember(Proof("the gate is shut", "p1", "saw it"))
    assert jem.count() == 1
    assert budnik.count() == 0
    assert jem.exists("p1")
    assert not jem.exists("p2")
    assert jem.path.name == "pool-jem-stein.metta"
    try:
        check_pool("bad pool!")
    except ValueError:
        pass
    else:
        raise AssertionError("bad pool name accepted")


def test_memory_api_pool_param(tmp_path, monkeypatch):
    from starlette.testclient import TestClient
    import runtime.chat as chat

    monkeypatch.setattr(chat, "METTA_PATH", tmp_path / "atoms.metta")
    monkeypatch.setattr(chat, "_store", None)
    monkeypatch.setattr(chat, "_stores", {})
    client = TestClient(chat.app)
    reply = client.post(
        "/memory/remember",
        json={"line": "remember that pools follow bootstrap docs", "pool": "jem-stein"},
    )
    assert reply.status_code == 200
    assert reply.json()["pool"] == "jem-stein"
    assert "pools follow bootstrap docs" not in client.get("/memory/atoms").json()["atoms"]
    pooled = client.get("/memory/atoms", params={"pool": "jem-stein"}).json()["atoms"]
    assert "pools follow bootstrap docs" in pooled
    bad = client.get("/memory/atoms", params={"pool": "NOPE!"})
    assert bad.status_code == 400


def test_choose_memories_recency_breaks_ties():
    from runtime.live_prompt import choose_memories

    claims = ["alpha keeps the north watch", "bravo keeps the north watch"]
    picked = choose_memories(claims, "who keeps the north watch?")
    assert picked[0] == "bravo keeps the north watch"
    # Overlap still dominates recency.
    picked2 = choose_memories(["zzz gate shut", "the gate is shut"], "is the gate shut?")
    assert picked2[0] == "the gate is shut"


def test_compress_tape_round_trip():
    from runtime.mind.compress import compress_tape, tape_token_count

    messages = [{"role": "user", "content": f"line {i} " + "x" * 40} for i in range(20)]
    out = compress_tape(messages, lambda span: "one summary paragraph", keep_last=4)
    assert out is not None
    assert out[0]["content"].startswith("compressed: one summary paragraph")
    assert len(out) == 5
    assert out[-1] == messages[-1]
    assert tape_token_count(messages) > tape_token_count(out)
    assert compress_tape(messages[:5], lambda span: "x", keep_last=4) is None
    assert compress_tape(messages, lambda span: "") is None
