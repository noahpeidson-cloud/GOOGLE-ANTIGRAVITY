# Memory Leak Debugging
Source: C:\Users\noahp\.gemini\config\plugins\chrome-devtools-plugin\skills\memory-leak-debugging\SKILL.md

Diagnoses and resolves memory leaks in JavaScript/Node.js applications.
Core principles:
- 0 detached DOM nodes
- Clear all event listeners on unmount (window.removeEventListener)
- Abort in-flight fetch controllers (AbortController)
- Clear timers (clearTimeout/clearInterval)
- Clean up closures and global references
