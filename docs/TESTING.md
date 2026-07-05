
[Guidelines](../Guidelines.md)

# Guideline: Testing

**TL;DR**

Our test suite must serve as a reliable safety net without restricting development. Tests should be expressive, have clear boundaries, run quickly, and fail only for useful reasons:

- **Expressive.** A test should clearly communicate what it protects so that it can be understood quickly.
- **Clear boundaries.** Difficulty in writing a test often indicates that a module requires a better structure.
- **Fast and reliable.** No flakes, no ten-minute suites.
- **Fails for useful reasons.** Red means broken, not "you renamed a private method."

**Behavior is what the caller observes through the public interface.** This interface includes function signatures, API endpoints, CLI commands, or exported libraries.

**Default rule:** ***test behavior at the component boundary through the public interface.*** Use unit and component tests for internal logic. Use System and End-to-End (E2E) tests only for critical user paths that span multiple components.

> [!IMPORTANT]
> Put it into practice
>
> *Deep Dives*
>
> - [Guideline: Flaky Tests](Guideline_%20Testing/Guideline_%20Flaky%20Tests.md)
> - [Test classification and architecture](Guideline_%20Testing/Test%20classification%20and%20architecture.md)
>
> *Languages & Frameworks*
>
> - [Pytest guidelines](Guideline_%20Coding%20Guidelines%20Python/Pytest%20guidelines.md)
> - [All things Vue](../Developer%20Documentation/UI%20Development/All%20things%20Vue.md)

---

# Principles

## Why we test

As stated in the [The Checkmk Engineering Manifesto](The%20Checkmk%20Engineering%20Manifesto.md), untested code is considered broken. We test to prevent regressions, enable confident refactoring, and provide fast feedback during development. Tests act as the first users of your API, highlighting issues with coupling early. Writing tests encourages a cleaner, more modular architecture.

**Focus on protecting user-facing behavior.** Tests should be written at the level where the behavior is defined, typically at the component boundary.

## What to test, and what not to

Every test is code that must be maintained. More tests are not automatically better.

**Earns a test:** user-visible flows and contracts, branching logic, error and failure paths, module boundaries where a change on one side could silently break the other, and areas with a history of regressions.

**Doesn’t earn a test:** trivial code, third-party library internals, behavior already covered by other tests, or excessive parameter variations.

# Practice

## Picking the level

**The level is chosen by behavior, not by habit.** Start by naming the behavior the test protects, in a sentence a non-engineer could understand, then pick the level that can verify it honestly and cheaply. The [The Checkmk Engineering Manifesto](The%20Checkmk%20Engineering%20Manifesto.md) rule applies throughout: *low enough to pinpoint failures, high enough to survive a restructure.*Ask where the behavior under test lives. For most of our code it lives at the public interface of a single component, and that is where the test belongs. Tests at that boundary survive internal refactors and still catch real regressions. That ratio is what makes them the suite's workhorse.

**Testing internal classes directly often gives less confidence than testing the component's public surface.** If the public interface is a Python API, use unit tests against that API. For web servers or CLIs, test the running process through its REST endpoints or command-line interface. 

**Verify each behavior once at the most appropriate level.** Testing the same behavior at multiple levels increases execution time and maintenance without adding value. If tests overlap, remove the higher-level test. System and E2E tests verify paths across several components. Use them sparingly as they are slower, more expensive to maintain, and prone to instability. *Limit these tests to the most critical workflows*.

For the definitions of unit, component, integration, system, and E2E tests, see: [Test classification and architecture](Guideline_%20Testing/Test%20classification%20and%20architecture.md)

## Runtime expectations

- A single unit test: 1–10 ms each.
- Component suite: under 10 minutes.
- Integration suite: under 10 minutes.
- System suite: under 30 minutes, critical path only.

A fast, reliable test suite is essential. If a test exceeds its time budget, it often indicates a need for better design rather than more time.

## Testing through the public surface

Test observable behavior such as inputs, outputs, and visible side effects. Avoid testing private methods. *Good tests break when the outcome is wrong, not when the internal implementation changes.*

**For private functions, test through the public surface.** If a private function is complex enough to require direct testing, consider moving it into its own module with its own public API. While exceptions exist for complex internal algorithms, the default should be to promote the code or test through the existing interface.

## Dependencies: doubles, injection, and patching

Most code depends on other classes, services, or external systems. How you manage these dependencies determines whether a test will be easy to maintain during refactoring.

Decide first **how** to supply the collaborator (using dependency injection or patching) and then **what** to supply (a real instance, fake, stub, or mock).

**Terminology for what you supply.** Most of what engineers call "a mock" is really a stub.

- **Stub** - returns canned answers.
- **Fake** - a working lightweight implementation (in-memory database, deterministic clock, fake HTTP server).
- **Mock** - a stub that additionally verifies how it was called.

**Mocks should generally be avoided.** They often depend on implementation details rather than behavior and can cause issues with development tools like static analysis.

**Dependency injection is the preferred method.** It makes dependencies explicit and improves code structure. Patching should be avoided as it couples the test to internal import logic, making refactoring harder.

**When patching is acceptable:** third-party code you don't own, any code owned by checkmk is not considered third-party code; genuine external boundaries (time, randomness, filesystem, network) where a fake isn't worth building or no good library exists to ease testing.

**When patching is a red flag:** patching your own internals; patching private functions; patching checkmk code from a different package/component.

**Pragmatism.** For legacy code that is difficult to restructure, patching is an acceptable compromise. Treat this as technical debt rather than a best practice for new code.

## Designing for testability without over-engineering

Design for testability without sacrificing code readability. If code is difficult to test, it usually indicates a structural problem that should be addressed.

**Useful seams:** I/O boundaries, time, randomness, external services, anything whose behavior you want to vary in tests, or that will vary in production.

**Redundant seams:** dependency injection for pure functions, interfaces around trivial collaborators that have one implementation forever, factories that exist only so a test can substitute a mock.

A seam is justified if the behavior varies in production or represents a genuine external boundary. Avoid adding seams solely to facilitate testing.

## The shape of a single test

**One behavior per test.** If you can't name the behavior in a short sentence, the test is doing too much. Split it.

**Use the Arrange-Act-Assert pattern.** These sections should be clear and visually distinct without requiring explicit comments.

**Names should describe behavior.** A test name should clearly explain what broke. Use descriptive sentences like "Discount is applied for gold members" instead of technical descriptions like "calculate\_price returns 150".

**Assertions should target observable outcomes.** Focus on API responses, UI changes, or visible side effects rather than internal call sequences.

**Keep assertions simple.** Failure messages should provide clear information about what broke. A single, focused assertion is better than multiple vague ones.
