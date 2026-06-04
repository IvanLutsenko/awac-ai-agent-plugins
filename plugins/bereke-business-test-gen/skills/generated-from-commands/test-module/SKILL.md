---
name: bereke-business-test-gen-test-module
description: Покрытие unit тестами всех классов модуля где есть смысл у тестов. Use when the user invokes /test-module.
version: 0.1.0
---

> Converted from Claude Code command `/test-module`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

## Задача

Создать unit тесты для ВСЕХ классов модуля, где unit тесты имеют смысл.

Включает:
- ✅ **Бизнес-логика:** ViewModel, UseCase, Interactor, Repository
- ✅ **Utils с логикой:** Validators, Formatters, Helpers
- ✅ **State machines**
- ✅ **Custom delegates**
- ✅ **Mappers со сложной логикой**
- ✅ **Cache implementations**

Исключает:
- ❌ UI компоненты (Activity, Fragment, Composable)
- ❌ Data classes без логики
- ❌ DI modules
- ❌ Константы/Enums без логики
- ❌ Простые Builder классы
- ❌ Sealed classes без логики

## Workflow

### Шаг 1: Загрузи стандарты

**Быстрая шпаргалка** (начни с этого - 50 строк):
```
!cat ~/.claude/plugins/marketplaces/awac-claude-code-plugins/plugins/bereke-business-test-gen/standards/android-kotlin-quick-ref.md
```

**Полное руководство** (если нужны детали - 600+ строк):
```
!cat ~/.claude/plugins/marketplaces/awac-claude-code-plugins/plugins/bereke-business-test-gen/standards/android-kotlin.md
```

### Шаг 2: Полное сканирование модуля

Найди ВСЕ Kotlin файлы в модуле:

```bash
find {module_path}/src/main -type f -name "*.kt" | grep -v "/di/" | grep -v "/models/"
```

### Шаг 3: Классификация классов

Для каждого найденного файла:

1. **Прочитай файл** - понять содержимое
2. **Классифицируй** по категориям:

**Категория A - Требуют тестов (высокий приоритет):**
- ViewModel
- UseCase
- Interactor
- Repository

**Категория B - Требуют тестов (средний приоритет):**
- Validator (содержит логику валидации)
- Formatter (содержит логику форматирования)
- Util/Helper с логикой
- Cache implementations
- State machines
- Custom delegates

**Категория C - НЕ требуют тестов:**
- Data class (простые DTO)
- DI modules (Koin/Dagger)
- Activity/Fragment
- Composable функции
- Enum без логики
- Sealed class без логики
- Constants
- Simple mappers (только присваивание полей)

### Шаг 4: Критерии "имеет смысл тестировать"

Класс требует тестов если:
- ✅ Содержит if/when условия
- ✅ Содержит циклы
- ✅ Содержит математические операции
- ✅ Содержит string манипуляции
- ✅ Содержит логику трансформации данных
- ✅ Координирует другие компоненты
- ✅ Управляет состоянием
- ✅ Содержит async операции (Flow, suspend)

Класс НЕ требует тестов если:
- ❌ Только data class поля
- ❌ Только UI код (@Composable)
- ❌ Только DI конфигурация
- ❌ Только константы
- ❌ Простой mapper (field.copy())

### ⚠️ КРИТИЧЕСКАЯ ПРОВЕРКА: По методам в каждом классе!

**Не тестируй весь класс сразу!** Проверь каждый public метод:

```
Перед созданием теста спрашивай:

1. Возвращает ли метод значение?
   ✅ fun validate(phone: String): Boolean  → ТЕСТИРОВАТЬ
   ❌ fun logEvent(name: String)  → ПРОПУСТИТЬ (void)

2. Может ли быть замокирована зависимость?
   ✅ api.getStatus() внутри метода  → ТЕСТИРОВАТЬ
   ❌ Firebase.track() SDK вызов  → ПРОПУСТИТЬ

3. Есть ли логика для асёрта?
   ✅ if (x > 0) return true  → ТЕСТИРОВАТЬ
   ❌ просто receiver.call()  → ПРОПУСТИТЬ

ВСЕ ДА? → создавай тест
ХОТЯ БЫ ОДИН НЕТ? → пропусти метод (нечего проверять)
```

**Типичный класс:**
```kotlin
class PaymentValidator {
    // ✅ ТЕСТИРУЕМ - возвращает значение, логика
    fun isCardValid(card: String): Boolean {
        return card.length == 16 && card.all { it.isDigit() }
    }

    // ❌ ПРОПУСКАЕМ - void, нет return
    fun reportCardUsage(card: String) {
        analytics.track("card_used")
    }
}
```

### Шаг 5: Анализ примера

**Требует теста:**
```kotlin
// Validator с логикой
class PhoneValidator {
    fun validate(phone: String): Boolean {
        if (phone.isEmpty()) return false
        val cleanPhone = phone.filter { it.isDigit() }
        return cleanPhone.length in 10..11
    }
}

// Formatter с логикой
class CurrencyFormatter {
    fun format(amount: Double): String {
        return when {
            amount >= 1_000_000 -> "${amount / 1_000_000}M"
            amount >= 1_000 -> "${amount / 1_000}K"
            else -> amount.toString()
        }
    }
}

// Util с логикой
class DateUtils {
    fun isExpired(timestamp: Long): Boolean {
        val now = System.currentTimeMillis()
        return timestamp < now - EXPIRY_DURATION
    }
}
```

**НЕ требует теста:**
```kotlin
// Простой data class
data class User(val id: String, val name: String)

// DI module
val appModule = module {
    single { AuthRepository(get()) }
}

// Простой mapper
fun UserDTO.toModel() = User(
    id = this.id,
    name = this.name
)

// Константы
object Constants {
    const val API_URL = "https://api.example.com"
}
```

### Шаг 6: Создание плана

Создай план в TodoWrite, сгруппированный по приоритетам:

```
=== Категория A: Бизнес-логика (8 классов) ===
1. AuthViewModel - нужен BaseTest + 3 файла
2. LoginUseCase - нужен тест
3. AuthInteractor - нужен тест
4. AuthRepository - уже покрыт ✅
...

=== Категория B: Utils и helpers (5 классов) ===
9. PhoneValidator - нужен тест
10. AmountFormatter - нужен тест
11. SessionCache - нужен тест
...

=== Категория C: Не требуют тестов (12 классов) ===
- UserDTO (data class)
- AppModule (DI)
- UserMapper (простой)
...

Итого к покрытию: 13 классов
```

### Шаг 7: Параллельная генерация тестов (NEW!)

**ПАРАЛЛЕЛЬНАЯ ГЕНЕРАЦИЯ ПО БАТЧАМ** для ускорения:

#### Шаг 7.1: Разбей классы на батчи

```python
classes_to_test = [... список из TodoWrite категорий A и B ...]
batch_size = 3-5 классов  # Оптимальный размер батча
batches = split(classes_to_test, batch_size)

# Пример: 15 классов → 3 батча по 5 классов
# Batch 1: [AuthViewModel, LoginUseCase, AuthInteractor, AuthRepository, UserValidator]
# Batch 2: [SessionCache, PhoneValidator, AmountFormatter, DateUtils, CryptoHelper]
# Batch 3: [PaymentInteractor, DocumentRepository, BiometricHelper, TokenManager, OtpValidator]
```

#### Шаг 7.2: Запусти батчи параллельно

Для каждого батча:

```python
# ПАРАЛЛЕЛЬНО через Task tool (SINGLE MESSAGE, MULTIPLE CALLS!)
for class_file in batch:
    Task(
      subagent_type="test-engineer",
      model="sonnet",
      prompt="Generate test for {class_file} with full coverage loop.
              Use template matching for simple methods.
              Target: 80%+ coverage, 3.0+ quality score",
      run_in_background=false  # Параллельно в одном сообщении!
    )

# Claude Code выполнит все Task calls в батче ПАРАЛЛЕЛЬНО!
```

**Example**:
```python
# Single message with 5 parallel Task calls:
Task(subagent_type="test-engineer", prompt="Generate test for AuthViewModel...")
Task(subagent_type="test-engineer", prompt="Generate test for LoginUseCase...")
Task(subagent_type="test-engineer", prompt="Generate test for AuthInteractor...")
Task(subagent_type="test-engineer", prompt="Generate test for AuthRepository...")
Task(subagent_type="test-engineer", prompt="Generate test for UserValidator...")
```

#### Шаг 7.3: После завершения батча - общая компиляция

```bash
# Запусти тесты для всего модуля (ONE TIME per batch)
./gradlew :{module}:testDebugUnitTest
```

#### Шаг 7.4: Повтори для следующего батча

```
LOOP через все батчи:
  1. Запусти параллельную генерацию (5 test-engineer agents)
  2. Дождись завершения всех agents
  3. Компилируй модуль один раз
  4. Переходи к следующему батчу
```

**Performance Gains**:
- 15 классов последовательно: 15 × 2 мин = 30 минут
- 15 классов в 3 батча по 5: 3 × 6 мин = 18 минут (40% faster)
- С template matching: 3 × 4 мин = 12 минут (60% faster!)

**Notes**:
- Каждый test-engineer работает на отдельном классе (no conflicts)
- Batch size 3-5 оптимален (balance между параллелизмом и ресурсами)
- Compilation once per batch (vs once per class)

### Шаг 8: Приоритизация

Генерируй в порядке:

**1. Категория A (критичная бизнес-логика):**
- UseCase (чистая бизнес-логика)
- Interactor (координация)
- Repository (данные)
- ViewModel (UI логика)

**2. Категория B (вспомогательная логика):**
- Validators (критично для data integrity)
- Cache (важно для performance)
- Formatters
- State machines
- Utils/Helpers

### Шаг 9: Примеры тестов разных типов

**ОБЯЗАТЕЛЬНО соблюдай при создании всех примеров:**
- ✅ @DisplayName для каждого теста
- ✅ Given-When-Then структура
- ✅ Truth assertions
- ✅ Максимум 80 символов на строку (detekt)
- ✅ Prefix `mock` для всех моков

**Validator:**
```kotlin
class PhoneValidatorTest {

    private lateinit var validator: PhoneValidator

    @BeforeEach
    fun setUp() {
        validator = PhoneValidator()
    }

    @DisplayName("When phone is valid 10 digits - Then returns true")
    @Test
    fun phoneValid10Digits_returnsTrue() {
        // Given
        val phone = "1234567890"

        // When
        val result = validator.validate(phone)

        // Then
        assertThat(result).isTrue()
    }

    @DisplayName("When phone is empty - Then returns false")
    @Test
    fun phoneEmpty_returnsFalse() {
        // Given
        val phone = ""

        // When
        val result = validator.validate(phone)

        // Then
        assertThat(result).isFalse()
    }

    @DisplayName("When phone has formatting characters - Then validates cleaned number")
    @Test
    fun phoneWithFormatting_validatesCleanedNumber() {
        // Given
        val phone = "+7 (123) 456-78-90"

        // When
        val result = validator.validate(phone)

        // Then
        assertThat(result).isTrue()
    }
}
```

**Formatter:**
```kotlin
class CurrencyFormatterTest {

    private lateinit var formatter: CurrencyFormatter

    @BeforeEach
    fun setUp() {
        formatter = CurrencyFormatter()
    }

    @DisplayName("When amount is millions - Then formats with M suffix")
    @Test
    fun amountMillions_formatsWithM() {
        // Given
        val amount = 2_500_000.0

        // When
        val result = formatter.format(amount)

        // Then
        assertThat(result).isEqualTo("2.5M")
    }

    @DisplayName("When amount is thousands - Then formats with K suffix")
    @Test
    fun amountThousands_formatsWithK() {
        // Given
        val amount = 5_500.0

        // When
        val result = formatter.format(amount)

        // Then
        assertThat(result).isEqualTo("5.5K")
    }
}
```

**Cache:**
```kotlin
@ExperimentalCoroutinesApi
class SessionCacheTest {

    private lateinit var cache: SessionCache

    @BeforeEach
    fun setUp() {
        cache = SessionCache()
    }

    @AfterEach
    fun tearDown() {
        FlowTestUtils.cleanupFlowResources()
    }

    @DisplayName("WHEN data is set THEN cache emits new value")
    @Test
    fun dataSet_cacheEmitsNewValue() = runTest {
        // Given
        val expected = SessionData(userId = "123")

        // When
        cache.setSession(expected)

        // Then
        cache.sessionFlow.test {
            val item = awaitItem()
            assertThat(item).isEqualTo(expected)
            cancelAndIgnoreRemainingEvents()
        }
    }
}
```

### Шаг 10: Итоговый отчет

```markdown
## ✅ Полное покрытие модуля: {MODULE_NAME}

### Статистика

**Всего Kotlin файлов:** 35

**Категория A - Бизнес-логика:** 8 классов
- До: 3 покрыто (38%)
- После: 8 покрыто (100%) ✅

**Категория B - Utils и helpers:** 5 классов
- До: 0 покрыто (0%)
- После: 5 покрыто (100%) ✅

**Категория C - Не требуют тестов:** 22 класса
- Data classes: 8
- DI modules: 3
- UI components: 7
- Simple mappers: 4

**Итого покрытие:** 13/13 классов (100%) ✅

### Созданные тесты

#### Бизнес-логика
1. ✅ AuthViewModelBaseTest + 3 файла
2. ✅ LoginUseCaseTest
3. ✅ LogoutUseCaseTest
4. ✅ AuthInteractorTest
5. ✅ AuthRepositoryImplTest

#### Validators & Formatters
6. ✅ PhoneValidatorTest
7. ✅ AmountFormatterTest
8. ✅ DateFormatterTest

#### Cache & State
9. ✅ SessionCacheTest
10. ✅ AuthStateMachineTest

#### Utils
11. ✅ DateUtilsTest
12. ✅ StringUtilsTest
13. ✅ CryptoHelperTest

### Классы не требующие тестов

**Data classes (8):**
- UserDTO, AuthResponseDTO, SessionData, ...

**DI modules (3):**
- AppModule, NetworkModule, ...

**UI components (7):**
- LoginScreen.kt, AuthActivity.kt, ...

**Simple mappers (4):**
- UserMapper.kt, AuthMapper.kt, ...

### Рекомендации

1. Запустить все тесты: `./gradlew :{module}:test`
2. Проверить покрытие: `./gradlew :{module}:koverHtmlReport`
3. Целевое покрытие: 80%+ для бизнес-логики
```

## Пример использования

```bash
# Покрыть весь модуль
/test-module-all feature/auth

# Покрыть impl модуль
/test-module-all feature/qr-signing/qr-signing-impl
```

## Критические требования

При генерации ВСЕХ тестов соблюдай:
- ✅ @DisplayName (без backticks)
- ✅ Given-When-Then структура
- ✅ Truth assertions
- ✅ Префикс mock для моков
- ✅ FlowTestUtils для Flow
- ✅ Полный tearDown с cleanupFlowResources
- ✅ Happy path + error handling + edge cases
- ✅ Анализируй каждый класс - тестировать ли его
- ✅ **Пакет теста = пакет исходного класса** (только путь меняется)
- ✅ Тестировать только PUBLIC методы (минимум 1 happy path + 1 error case)

## Проверка качества после генерации

После завершения генерации всех тестов:

```bash
# 1. Проверка синтаксиса
./gradlew :{module}:compileDebugUnitTestKotlin

# 2. Проверка линтера и удаление неиспользуемых импортов
./gradlew :{module}:lintDebugUnitTest

# 3. Запуск всех тестов
./gradlew :{module}:testDebugUnitTest

# 4. Проверка покрытия кода
./gradlew :{module}:koverVerify
./gradlew :{module}:koverHtmlReport  # отчет в build/reports/kover/html/
```

**Если лinter нашел unused imports:**
- Удали их автоматически через Edit
- Переблюдай логику того что осталось

**Если тесты не компилируются:**
- Проверь типы параметров
- Убедись что все импорты правильные
- Перепроверь синтаксис Given-When-Then блоков

**Целевое покрытие:** >= 70% (стремись к 100%)

### Вывод покрытия по модулю

После успешного завершения всех тестов ОБЯЗАТЕЛЬНО выведи итоговое покрытие модуля:

```bash
# Извлекаем общее покрытие из XML отчета
COVERAGE_FILE="build/reports/kover/report.xml"

# Получаем LINE и INSTRUCTION покрытие модуля
echo "📊 Покрытие модуля {MODULE_NAME}:"
grep -E 'counter type="(LINE|INSTRUCTION)"' "$COVERAGE_FILE" | head -2
```

Выведи в формате:
```
📊 Итоговое покрытие модуля {MODULE_NAME}:
- LINE coverage: XX.X%
- INSTRUCTION coverage: XX.X%

✅ Статус: Покрытие [на уровне/ниже] целевого (70%)
```

**Интерпретация результатов:**
- ✅ > 80% - Отличное покрытие
- ✅ 70-80% - Целевое покрытие достигнуто
- ⚠️  60-70% - Хорошее, но можно добавить edge cases
- ❌ < 60% - Требуется добавить тесты для critical paths

## ✨ BONUS: Автоматическое достижение 100% покрытия

Если хочешь достичь 100% покрытия - используй этот workflow для итеративной генерации:

### Шаг 1: Сгенерируй базовые тесты

```bash
# Создай первый набор тестов обычным способом
/test-module-all feature/auth
```

### Шаг 2: Генерируй Kover отчет

```bash
# Запусти Kover с XML отчетом
./gradlew :{module}:koverXmlReport

# XML будет в: build/reports/kover/report.xml
```

### Шаг 3: Найди методы с недостаточным покрытием

```bash
# Показать методы где missed > 0:
grep -E '<method.*missed="[1-9]"' build/reports/kover/report.xml | grep -oP 'name="\K[^"]*'

# Или все методы с их покрытием:
grep '<method' build/reports/kover/report.xml | grep -oP 'name="\K[^"]*' | head -20
```

Вывод покажет методы типа:
```
getFcmToken
postMessageStatus
deleteToken
onIntentReceived
```

### Шаг 4: Для каждого uncovered метода - генерируй тест

```bash
# Для каждого метода найденного в Шаге 3:
/generate-test feature/auth/data/repositories/AuthRepository.kt

# Сосредоточься на методе `getFcmToken`:
# - Happy path: успешное получение токена
# - Error case: токен недоступен
# - Edge case: null/empty результат
```

### Шаг 5: Проверь обновленное покрытие

```bash
# Перегенерируй отчет
./gradlew :{module}:koverXmlReport

# Проверь новый результат
grep -c '<method' build/reports/kover/report.xml  # всего методов
grep -c 'missed="0"' build/reports/kover/report.xml  # полностью покрыто
```

### Шаг 6: Повторяй пока не будет 100%

```bash
# Показать итоговое покрытие
./gradlew :{module}:koverVerify

# Если не прошло (< 100%):
# 1. Повтори Шаг 3 (найди новые uncovered методы)
# 2. Повтори Шаг 4 (генерируй тесты)
# 3. Повтори Шаг 5 (проверь результаты)

# Когда пройдет - готово! ✅
```

### Пример полного цикла

```bash
# 1. Начальная генерация
/test-module-all feature/auth

# 2. Первая итерация
./gradlew :feature:auth:koverXmlReport
grep '<method' build/reports/kover/report.xml | wc -l  # => 15 методов
grep -E 'missed="[1-9]"' build/reports/kover/report.xml | wc -l  # => 6 методов не покрыто

# 3. Генерируем тесты для 6 методов (Шаг 4)
/generate-test feature/auth/data/AuthRepository.kt  # getFcmToken
/generate-test feature/auth/data/AuthRepository.kt  # postMessageStatus
# ... еще 4 метода

# 4. Вторая итерация
./gradlew :feature:auth:koverXmlReport
grep -E 'missed="[1-9]"' build/reports/kover/report.xml | wc -l  # => 2 метода

# 5. Генерируем тесты для оставшихся 2
/generate-test feature/auth/domain/AuthInteractor.kt  # método_x
/generate-test feature/auth/domain/AuthUseCase.kt    # método_y

# 6. Проверка финального результата
./gradlew :feature:auth:koverVerify  # ✅ BUILD SUCCESSFUL
```

### Автоматизированный скрипт (опционально)

Если надоел ручной процесс - создай скрипт:

```bash
#!/bin/bash
MODULE="feature:auth"
COVERAGE_TARGET=100

while true; do
    # 1. Генерируй отчет
    ./gradlew :${MODULE}:koverXmlReport

    # 2. Найди uncovered методы
    UNCOVERED=$(grep -E 'missed="[1-9]"' build/reports/kover/report.xml | \
                 grep -oP 'name="\K[^"]*' | sort -u)

    # 3. Если нет uncovered - выход
    if [ -z "$UNCOVERED" ]; then
        echo "✅ 100% coverage achieved!"
        break
    fi

    # 4. Для каждого uncovered метода - даю инструкцию генерировать тест
    echo "❌ Found uncovered methods: $UNCOVERED"
    echo "📝 Generate tests for these methods:"
    echo "$UNCOVERED" | head -5  # Show max 5 для не затопить user

    # 5. User должен запустить /generate-test для каждого
    # (полная автоматизация требует интеграции AI model внутри скрипта)
    echo "Run: /generate-test {class-with-these-methods}"
    break
done
```

### ⚠️ Важные моменты

1. **Kover парсинг:** XML структура может отличаться по версиям
   ```xml
   <method name="methodName">
     <counter type="LINE" missed="0" covered="5"/>  ← это важно
   </method>
   ```

2. **Missed vs Covered:**
   - `missed="0"` = полностью покрыто ✅
   - `missed="1"` = 1 инструкция не покрыта ❌

3. **LINE vs INSTRUCTION:**
   - LINE покрытие используется для целевого процента (70%)
   - INSTRUCTION покрытие дает более точные результаты

4. **Повторяющийся процесс:**
   - Каждый раз новые тесты покрывают не только целевой метод, но и другие
   - Итоговое покрытие может быстро расти
   - Обычно 2-3 итерации достаточно для 100%
