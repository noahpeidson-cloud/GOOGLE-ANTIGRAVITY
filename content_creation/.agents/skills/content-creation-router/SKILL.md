---
name: content-creation-router
description: >
  MANDATORY TRIGGER: Activate this skill anytime the user asks to "process a vlog", "run the video pipeline", or mentions "content creation". It provides the exact sequence of tools and skills you must chain together to succeed without guessing.
---

# Content Creation Router

When operating in the `/content_creation` track, you MUST follow this sequence of skills and operations. Do not hallucinate generic video processing logic.

## The Optimal Video Pipeline Sequence

1. **Ingestion (Local Code)**
   - First, inspect and run `ffmpeg_processor.py` to handle initial video formatting and LUFS normalization (-14).
   
2. **Quality Assurance (Multi-Agent Teamwork)**
   - Next, read the `teamwork-preview` skill (or invoke a teamwork subagent) to orchestrate a parallel review of the output. 
   - You must instruct the teamwork agent to programmatically verify the LUFS levels and 9:16 safe zones.

3. **Distillation (Skill Creation)**
   - If a new, complex video task is achieved during this process, you must proactively invoke the `workflow-skill-creator` skill to package the new capability into a local `.agents/skills` package for the future.

4. **Web Dashboard Updates (Web APIs)**
   - If asked to update the local video reviewing UI dashboard, you MUST read the `modern-web-guidance` and `chrome-devtools` skills before editing any React/HTML code.

By following this routing script, you guarantee the platform utilizes the best tools at the right times.
