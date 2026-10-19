### Crash: IllegalStateException when the payment form finishes from a Compose host

**Basic info**:
- Exception: `IllegalStateException: No parent implements HostContract`
- Affected users: unknown (REST fallback, no counters)
- App version: 2.4.0 (310)
- Android API: 34
- Component: UI / legacy Fragment navigation

**Stack trace analysis**:
- `FragmentExt.kt:77` — `parentFragment?.findHost(type) ?: throw IllegalStateException(...)`: the parent chain ends with `null`.
- `ActionFragment.kt:172` — `findHost<HostContract>().replaceOnTop(fragment)`.
- `FormFragment.kt:182` — `finish(fragment)` calls `showDestination`.
- `PaymentViewModel.kt:391` — `onSuccess` after `repository.postDocument(document)`.

**Checked files**:
- `core/actions/src/main/java/com/example/actions/ActionFragment.kt`: lines 160-173 (Jane Doe, `6aba3bd07a`)
- `app/src/main/java/com/example/payments/PaymentComposeLauncher.kt`: lines 24-34 (John Smith, `ac8bf1f3f5`)

**Executed commands**:
- `git blame -L 160,173 origin/main -- core/actions/src/main/java/com/example/actions/ActionFragment.kt`
- `git log origin/main --oneline -8 -- core/actions/src/main/java/com/example/actions/ActionFragment.kt`

**Root cause**:
`PaymentComposeLauncher` puts `PaymentFragment` directly into a Compose `NavHost` through `AndroidFragment`, so the fragment has no parent fragment. After a successful submit the form calls `showDestination`, which requires an ancestor implementing `HostContract` and throws when the parent chain ends.

**Proposed fix**:

**Before:**
```kotlin
findHost<HostContract>().replaceOnTop(fragment)
```

**After:**
```kotlin
findHostOrNull<HostContract>()?.replaceOnTop(fragment) ?: onHostMissing()
```

**Assignee**: Jane Doe
- Source: `git blame origin/main -- core/actions/.../ActionFragment.kt -L 160,173` — line 172 → Jane Doe, `6aba3bd07a`.
- Alternative: John Smith — blame `PaymentComposeLauncher.kt:26`.

**Context & Prevention**:
- **Trigger**: the user opens a payment from the Compose services screen, fills the form and submits it.
- **Why now**: a refactor replaced the direct fragment replace with a host lookup and did not account for the Compose-hosted entry point.
- **Prevention**: use a null-safe host lookup in fragments that can be hosted through `AndroidFragment`.

## JIRA Brief

**Crash**: IllegalStateException after a successful payment submit from the Compose host
**Component**: payments / ui-navigation
**Assignee**: Jane Doe (git blame: core/actions/src/main/java/com/example/actions/ActionFragment.kt:172)

**Problem**: The app crashes after the document is already created on the server.

**Stack trace**:
```
IllegalStateException: No parent implements HostContract
  at FragmentExtKt.findHost (FragmentExt.kt:77)
  at ActionFragment.showDestination (ActionFragment.kt:172)
  at FormFragment.finish (FormFragment.kt:182)
```

**Cause**: `PaymentComposeLauncher.kt:26` hosts the fragment without a host fragment.

**Fix**:
```kotlin
findHostOrNull<HostContract>()?.replaceOnTop(fragment) ?: onHostMissing()
```

**Reproduction**:
1. Open the services screen and tap Pay.
2. Fill the form and submit.
3. Success message, then the crash.

**Firebase**: https://console.firebase.google.com/project/example-project/crashlytics/app/android:com.example.app/issues/0123456789abcdef0123456789abcdef
