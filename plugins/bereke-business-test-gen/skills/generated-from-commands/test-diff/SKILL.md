---
name: bereke-business-test-gen-test-diff
description: Генерация тестов только для измененных файлов в PR (vs target branch). Use when the user invokes /test-diff.
version: 0.1.0
---

> Converted from Claude Code command `/test-diff`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Test Diff Command

Генерирует unit тесты только для новых/измененных Kotlin файлов в текущей ветке.
Идеально для PR workflow — тестируй только то, что изменил.

## Аргументы

- `--branch <target>` — target branch для сравнения (default: `origin/master`)
- `--dry-run` — только показать какие файлы будут обработаны, без генерации

## Примеры

```bash
/test-diff                           # vs origin/master
/test-diff --branch origin/develop   # vs develop
/test-diff --dry-run                 # preview без генерации
```

## Алгоритм

### Шаг 1: Получить измененные файлы

```bash
# Получить список измененных .kt файлов (исключая тесты)
git diff ${TARGET_BRANCH} --name-only --diff-filter=ACMR -- '*.kt' | \
  grep -v 'Test\.kt$' | \
  grep -v '/test/' | \
  grep 'src/main'
```

### Шаг 2: Фильтрация через test-skip-analyzer

Для каждого файла вызвать агент `test-skip-analyzer`:
- Input: путь к файлу
- Output: `{ skip: boolean, reason: string, confidence: number }`

**Skip если**:
- DTO/Entity/Response/Request без логики
- DI Module
- Activity/Fragment/Composable
- Constants/Config
- confidence > 0.8

### Шаг 3: Проверка существующих тестов

Для каждого НЕ-skipped файла:

```bash
# Найти существующий тест
SOURCE_FILE="src/main/java/kz/berekebank/feature/auth/AuthRepository.kt"
TEST_FILE=$(echo $SOURCE_FILE | sed 's|src/main|src/test|' | sed 's|\.kt$|Test.kt|')

if [ -f "$TEST_FILE" ]; then
  echo "UPDATE: $TEST_FILE"
else
  echo "CREATE: $TEST_FILE"
fi
```

### Шаг 4: Генерация/обновление тестов

**Для новых файлов** (тест не существует):
- Вызвать `/test-class <source_file>`

**Для измененных файлов** (тест существует):
1. Прочитать source file
2. Прочитать test file
3. Найти новые/измененные методы:
   ```bash
   git diff ${TARGET_BRANCH} -- ${SOURCE_FILE} | grep '^+.*fun '
   ```
4. Для каждого нового метода — добавить тест в существующий файл

### Шаг 5: Вывод результата

```
📊 Test Diff Report
═══════════════════════════════════════════════════════

Branch: feature/auth-improvements vs origin/master
Changed files: 12
Skipped (DTO/UI): 5
Testable: 7

📝 Generated Tests:
┌─────────────────────────────────────────────────────┐
│ File                          │ Action   │ Tests   │
├─────────────────────────────────────────────────────┤
│ AuthRepository.kt             │ CREATE   │ 8       │
│ LoginInteractor.kt            │ UPDATE   │ +3      │
│ TokenValidator.kt             │ CREATE   │ 5       │
│ OtpFormatter.kt               │ CREATE   │ 4       │
│ SessionManager.kt             │ UPDATE   │ +2      │
│ BiometricHelper.kt            │ CREATE   │ 6       │
│ CredentialsMapper.kt          │ SKIP     │ -       │
└─────────────────────────────────────────────────────┘

⏱️ Time: 4m 32s
📈 Coverage delta: +12.3% (estimated)

✅ Ready for PR!
```

## Dry Run Mode

При `--dry-run` выводится только план без генерации:

```
📋 Dry Run - Test Diff Plan
═══════════════════════════════════════════════════════

Branch: feature/auth vs origin/master

Files to process:
  ✅ CREATE test: AuthRepository.kt
  ✅ UPDATE test: LoginInteractor.kt (2 new methods)
  ⏭️ SKIP: AuthDto.kt (DTO without logic)
  ⏭️ SKIP: AuthModule.kt (DI module)
  ⏭️ SKIP: LoginActivity.kt (UI component)

Summary: 2 tests to create, 1 to update, 3 skipped

Run without --dry-run to generate tests.
```

## Интеграция с CI

Пример использования в GitHub Actions:

```yaml
- name: Generate tests for PR
  run: |
    claude "/test-diff --branch origin/${{ github.base_ref }}"
```

## Зависимости

- **test-skip-analyzer** — определяет skip/test
- **test-engineer** — генерирует тесты
- **test-coverage-analyst** — проверяет coverage

## Ограничения

- Работает только в git repository
- Требует доступ к target branch (fetch если нужно)
- Максимум 20 файлов за раз (для больших PR разбить на части)
