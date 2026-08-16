---
name: git-commits
description: >-
  Standard guidelines for creating clean, atomic, well-separated Git commits with
  Conventional Commits formatting and descriptive multi-line bodies. Use whenever
  committing code or when the user asks to commit changes.
---

# Git Commit Standards: Atomic & Well-Separated Commits

Always structure Git commits logically with clear architectural boundaries, conventional commit types, and descriptive bulleted bodies.

---

## 1. Commit Granularity & Separation Rules

Never create a single monolithic commit for multiple distinct layers of work. Separate commits logically by layer and concern:

1. **Refactoring & Removals**:
   - Isolating dead code deletion, provider removal, schema cleanups, and migrations.
   - Example: `refactor(phase-7): remove Printful integration and decouple master PNG production`

2. **Core Domain & Backend Infrastructure**:
   - Models, repositories, ports, adapters, and domain services.
   - Example: `feat(phase-7): implement multi-mockup listing asset architecture and API endpoints`

3. **API Routes & Schemas**:
   - HTTP routes, request/response DTOs, endpoint handlers, and validation logic.

4. **Frontend UI Components & State**:
   - Vue components, Pinia stores, Tailwind styling, modals, and user interactions.
   - Example: `feat(phase-7): build multi-mockup gallery grid, cover badges, and placement editor`

5. **Tests & Tooling**:
   - Unit, integration, and E2E test suites or CI configurations (can be bundled with their respective feature commit or separated for large test suites).

---

## 2. Commit Message Structure

Follow the Conventional Commits specification:

```text
<type>(<scope>): <concise action-oriented subject in present tense>

- <Bullet 1 explaining key change and rationale>
- <Bullet 2 listing API/schema changes>
- <Bullet 3 listing architectural decisions or UI enhancements>
- <Bullet 4 listing verification or test coverage>
```

### Commit Types

- `feat`: New feature or capability
- `fix`: Bug fix
- `refactor`: Code restructuring without functional changes
- `perf`: Performance improvement
- `test`: Adding or refactoring tests
- `chore`: Build tasks, dependency updates, configs
- `docs`: Documentation updates

---

## 3. Execution Workflow

1. **Verify All Tests Pass**: Run relevant test suites before committing.
2. **Review Working Tree**: Run `git status` to see all changed and untracked files.
3. **Explicit Staging**: Use `git add <file1> <file2> ...` to stage ONLY the files belonging to the specific atomic commit.
4. **Commit with Multi-Line Message**: Use `git commit -m "..."`.
5. **Repeat for Remaining Layers**: Stage and commit subsequent layers until working tree is clean.
6. **Verify Log**: Check `git log -n <count>` and `git status` to verify a clean working directory.
