# Test classification and architecture

# Test Types: Definitions

## Static Analysis

Linting, type checking, formatting, license header checks. These catch issues without executing code. They are repo scoped, and not visible from within the respective packages. If at all possible they should be integrated into bazel lint. It scales better and allows for a clean dependency structure.

## Package Tests

Package tests are scoped to a single package. They have no first-party dependencies beyond the package under test and its dependencies.

They live in that package's tests/ directory. This category **encompasses both unit tests and component** tests. The distinction matters for test design, but from the project's build and CI perspective they share the same properties: small, fast, closely linked to the code under test.

### Unit Tests

Test the API of a python library: a single function, method, or class in isolation. No running helper processes. Dependencies are replaced with test doubles (mocks, stubs, fakes) where necessary.

- **Dependencies**: No first party dependencies beyond those of the system under test itself.
- **Setup**: No additional infrastructure, no test-only services.
- **When to use**: Testing pure logic, algorithms, data transformations, parsers, formatters, individual utility functions
- **Where to find**: These tests should live in the respective package in the tests/ folder
- **Runtime target:** 1 - 10ms

### Component Tests

Test a package with its real package level dependencies wired together. For example, testing a service like the agent receiver daemon with its real serializers and validators, but without a running Checkmk site or any other application provided by another package.

These are the key distinctions from other test classes:

- **Distinction from unit tests:** Component tests exercise real interactions between classes rather than mocking them.
- **Distinction from integration tests:** The component tests add no additional package dependencies. But: They may create an actual runtime environment (of package internal applications).
- **Distinction from system tests:** No systems outside of the package are covered or required.

Properties:

- **Dependencies**: No additional dependencies beyond those of the system under test itself.
- **Setup**: Potentially some in-process fixtures; no running site
- **When to use**: Testing interactions within a bounded module, e.g. a complete check plugin pipeline (discovery + check function + parameters) or the agent receiver
- **Where to find**: These tests should live in the respective package in the tests/ folder
- **Runtime target:** < 30s, preferably faster.

### Directory Layout Within a Package

The structure within a package's tests/ directory depends on the package's needs. Possible variants:

- tests/test\_\<module\>.py — flat layout for simple packages
- tests/{unit,component}/... — when separating unit from component tests is useful
- tests/acceptance/... — for acceptance tests (see "Functional vs. Acceptance vs. Regression Tests")

Choose the simplest variant that fits the required complexity.

## Integration Tests

Test the interaction between two or more packages without requiring a run-time environment ( like a Checkmk site or real monitored systems). These verify that components from different packages properly integrate with one another (e.g. agent controller ↔ agent receiver, check engine ↔ plugin interface).

- **Dependencies**: Two or more first-party packages.
- **Setup**: No running site or real monitored systems. May use mocks, sockets, or lightweight in-process setups.
- **When to use**: Testing cross-package interfaces and contracts (e.g. REST-API endpoint and framework integration)
- **Where to find**: In tests/integration/
- **Runtime target:** < 30s, preferably faster.

## System Level Tests

Test the entire system from the user's perspective, or verify different aspects of the whole surface and parts of the system. These tests may exercise the full stack including the web server, site processes, and frontend rendering.

They include but are not limited to “End to End” and “Site” tests (see below). In general a system test may or may not be an “End to End” test, a “Site” test or both.

- **Dependencies**: A dedicated first party package to provide required functionality (see below)
- **Setup**: Running site and/or real monitored (third party) systems and/or browser automation (Playwright) and/or HTTP client
- **When to use**: Critical user workflows, cross-cutting features that span multiple subsystems, visual regression.

### End to End Tests

E2E tests interact with the system through its external interfaces: For example the GUI (via Playwright) or the REST API (via HTTP client). These are two entry points into the same system, not fundamentally different test types. In our case (testing Checkmk) E2E will almost always be site tests as they are simulating a real user scenario and therefore are most likely interacting with a site.

### Site Tests

System level tests that require one or more running Checkmk sites use a dedicated package providing the required libraries for site setup and interaction.

Tests so far referred to ascomposition tests are site tests where two or more sites interact in a distributed monitoring setup. There is no conceptual difference between tests that use one site (so far referred to as "integration tests") and those that use more than one (so far referred to as "composition tests").

> [!IMPORTANT]
> - We assume that we can have any number of test targets using any number of sites. As of today, for performance reasons most of them (have to) share their setup. However we do have more than one, and it would be desirable to have no practical limitation on how many we can have.
> - For Checkmk End to End tests and Site tests overlap heavily, but they are not the same *in general*. There may be System tests that are neither.

### Doctests

Doctests are **documentation, not tests**. They serve as executable examples that keep documentation accurate. Running them as part of the test suite is a documentation freshness check, not a testing strategy. Doctests must not be relied upon as the sole test coverage for any logic.

# Other Test dimensions

## Code-Proximate vs. Behaviour-Proximate Tests

Not all tests relate to the codebase in the same way. This has implications for how they are structured, who owns them and how they are written.

**Code-proximate tests** (mostly package tests, integration tests) are closely tied to the code they run. They mirror the code’s structure,  one test module per source module, grouped by package. Their primary stakeholders are the maintainers of that code. When the code moves or changes, the tests move and change along with it.

**Behavior-proximate tests** (mostly system level tests, acceptance tests) verify user-visible behavior and business requirements. They are organized by feature or workflow, not by source module. Their stakeholders may include QA, product management, or other teams beyond the original developers. They tend to have different styles (more scenario-driven, not tied to internal APIs) and different change control requirements (acceptance tests require explicit alignment before modifying the expected outcome).

This distinction is not a new test category, it cuts across the existing levels. But it explains why tests naturally differ in structure, ownership, and process.

## Functional/Regression vs. Acceptance vs. Performance Tests

These terms describe the **purpose** of a test, not its architectural structure. Any test at any level can serve **one or more** of these purposes:

**Functional tests** verify that a feature works as specified, **regression tests** verify that a previously fixed bug stays fixed. For functional and regression tests no special marking is required.The main difference is regression tests are created in hindsight.

**Acceptance tests** verify that a feature meets business/user requirements. They live in a dedicated acceptance/ directory. Their exact location can depend on the overall structure of the tests in question, but it must feature the acceptance/ path segment. Acceptance tests are not free to be adjusted by individual developers; changes that modify the expected outcome require explicit alignment with the stakeholders. This directory-based separation makes the constraint visible and enforceable (e.g. OWNERS files).

**Performance tests** verify that a functionality or workflow can be executed in a set amount of time and/or with a set amount of resources. This implies special runtime requirements for these tests, as the resource availability must be guaranteed by the CI to get reliable results. As a consequence the CI must be able to filter these targets (the current assumption is we can use tags for that).

# Checkmk-Specific Considerations

## Editions

### Artifact Tests

Inherently edition specific. Here we test that a given build artifact (edition) contains the expected files.

### Package Tests (unit + component)

These are **edition-agnostic**. The behavior of a module does not change between editions — only whether it is **deployed** changes. No skip\_if\_edition / skip\_if\_not\_edition markers. If a module exists, its tests run regardless of edition. In some corner cases the *edition enum* may be a straightforward parameter of a test case.

### Integration Tests

These are **edition-agnostic**. The question whether multiple components need to integrate with one another does not depend on an edition.

### System Tests

Currently they appear to be edition-specific, since they test deployed systems where the available feature set depends on the edition. However these tests should test **features** and that's how they should be organized (e.g.: We don't really have PRO specific tests, we have DCD specific tests).

All system test targets will be called in a parametrized way, specifying the site's edition. The setup should create the corresponding site(s). The tests should declare which feature they expect. The framework needs to provide means to do that. The framework has (centralized) access to the information which features are expected on which edition, and which edition is under test. It can then decide to run the tests, skip the tests, or raise an appropriate exception.

For performance reasons we currently run a lot of test "bundles" in one test run, sharing a site setup. Ideally, we could split these up into individual test targets with independent setup. For now put the tests in py\_libraries that are collected by one py\_test target. If and when we overcome the performance limitation we can run them as individual test targets.

For this purpose we create a test library **package** that provides the necessary fixtures for their setup:

- Automatic site creation and cleanup
- Site restart and configuration
- Log collection and crash report handling on failure
- The framework for feature-under-test declaration as outlined above

**All system tests are included in the target for every edition.** Every feature test suite shall declare the feature under test, and the framework takes the appropriate action.

## Free VS Nonfree

Not all of our Repo is GPLed. To facilitate the filtering, we put all proprietary code into the to level folder non-free/. Apart from this prefix, we want to keep architectural differences at a minimum. To keep the bazel targets as simple as possible, all targets that depend on non-free libraries should live below non-free/ themselves. As long as we have one single system test target depending on non-free and free code, it shall live under non-free/tests. The respective test libraries can live in either tier (consistent with the feature under test). 

## Repository Level Directory Layout

Apart from the structure within the packages:

```
{non-free/,}tests/
├── integration/
├── system/
│   ├── system-target-1/ # e.g. subfolder per target level tests
├── artifact/        # currently packaging
└── performance/
```

# Workflows

## CI - Test Discovery and Execution Model

#### Package Tests (Unit + Component)

Package tests are fully managed by Bazel. Their targets live inside packages and have explicit dependency graphs, so Bazel can determine which tests are affected by a change and which can be served from cache.

- **CV (Change Verification):** bazel test //packages/... — Bazel runs only what's affected, caches the rest. This is fast and scalable.
- **Post-merge:** Same as CV. No special handling needed.
- **Local dev:** Same command. Developers get the same caching benefits.

### Integration Tests (Cross-Package, No Site)

Integration tests in tests/integration/ also have Bazel targets with explicit dependencies on the packages they exercise. Discovery works the same as for package tests.

- **CV / Post-merge / Local dev:** bazel test //tests/integration/... //non-free/tests/integration/...   Bazel tracks dependencies and caches.

### System Level Tests (Site Tests, E2E, Artifacts)

System level tests are the hard case. Their Bazel targets do not necessarily depend on the libraries implementing the features they test. A Playwright test exercising host creation has no build-time dependency on cmk.gui.wato. Bazel's dependency-based cache invalidation therefore cannot reliably determine which system tests are affected by a given change, and should be disabled when running system tests (or we achieve the equivalent by having these test targets depend on the built Checkmk package). Rather than crafting the dependency tree to artificially reflect dependencies when to run specific tests, we leverage filtering by bazel tags. Bazel tags can be used to express relations like “If package cmk-xyz is changed, this test needs to run” or “This test should always be run in the middle chain” etc. Via setting specific tags on a test target, developers could hook into the CI allowing for concepts like (for example):

- **Conditional System Level CV**: Tests that are run during Change Validation, provided that the packages specified in the targets tags have been touched.
- **Unconditional System Level CV**: Tests that are run unconditionally during CV
- **System Level post-merge**: Tests that are run unconditionally post merge

The exact extent of this depends on various aspects that are subject to change (the existence of a middle chain, or CI resources).

## Local Development Workflow

The expected workflow for a developer making a change:

- **Always run:** Package tests for the affected package(s) bazel test //packages/cmk-\<pkg\>/.... Fast, cached, should be a habit.
- **When touching cross-package boundaries:** Integration tests  bazel test //tests/integration/... or a specific subset.
- **Rarely locally**: System level tests. These are slow and require site infrastructure. In general developers should rely on CI for these, but local execution should be possible (for example when actively working on the test itself or debugging a CI failure).

Static analysis (bazel lint, bazel build --config=mypy) runs at every level and is expected before every commit.
