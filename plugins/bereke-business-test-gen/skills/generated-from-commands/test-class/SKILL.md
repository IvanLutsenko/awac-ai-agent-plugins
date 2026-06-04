---
name: bereke-business-test-gen-test-class
description: Генерация unit теста для одного класса по корпоративным стандартам. Use when the user invokes /test-class.
version: 0.1.0
---

> Converted from Claude Code command `/test-class`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

## Задача

Сгенерировать unit тест для указанного класса, строго следуя корпоративным стандартам.

## Workflow

### Шаг 1: Загрузи стандарты

**Быстрая шпаргалка** (начни с этого):
```
!cat ~/.claude/plugins/marketplaces/awac-claude-code-plugins/plugins/bereke-business-test-gen/standards/android-kotlin-quick-ref.md
```

**Полное руководство** (если нужны детали):
```
!cat ~/.claude/plugins/marketplaces/awac-claude-code-plugins/plugins/bereke-business-test-gen/standards/android-kotlin.md
```

### Шаг 2: Анализ исходного класса

1. Прочитай исходный файл
2. **КРИТИЧНО:** Определи пакет класса:
   ```
   Например, если класс в:
   src/main/java/kz/berekebank/business/core/push/push_impl/data/repositories/PushRepository.kt

   Пакет: kz.berekebank.business.core.push.push_impl.data.repositories

   Тест ДОЛЖЕН быть в ТОМ ЖЕ пакете:
   src/test/kotlin/kz/berekebank/business/core/push/push_impl/data/repositories/PushRepositoryTest.kt

   Только путь меняется: src/main → src/test
   Пакет остается ИДЕНТИЧНЫМ исходному классу!
   ```

3. Определи слой архитектуры:
   - **ViewModel** - управление UI состоянием
   - **UseCase** - бизнес-логика
   - **Interactor** - координация UseCase
   - **Repository** - работа с данными
   - **Mapper** - преобразование данных
   - **Validator** - валидация
   - **Другое** - util, formatter и т.д.

4. Найди все зависимости для мокирования
5. Определи публичные методы для тестирования (только public!)
6. Проверь использование корутин и Flow

### ⚠️ КРИТИЧЕСКАЯ ПРОВЕРКА перед тестированием КАЖДОГО метода

**Для каждого public метода проверь:**

```
□ Возвращает значение? (не void)
  ✅ fun getKey(): String  → ТЕСТИРОВАТЬ
  ❌ fun logEvent(name: String)  → ПРОПУСТИТЬ (void method)

□ Может быть замокирована его зависимость?
  ✅ api.getStatus()  → можно замокировать → ТЕСТИРОВАТЬ
  ❌ Firebase.track()  → только instrumentation test

ВАЖНО для Repository/UseCase/Interactor:
✅ ВСЕГДА тестируй wrapper/forward методы - они часть публичного API
✅ Используй Turbine для Flow<T> и Flow<PagingData<T>>
✅ Можешь замокировать зависимость? → создавай тест

Примеры wrapper методов которые НУЖНО тестировать:
✅ suspend fun getData() = api.getData()  // проверяем вызов API
✅ fun getFlow() = repository.dataFlow     // проверяем Flow с Turbine
✅ suspend fun loadFields() = api.getFields()  // проверяем параметры

Пропускай ТОЛЬКО если:
❌ Void метод без side effects
❌ Private метод (покрыть косвенно)
❌ Системный вызов (Firebase, NotificationManager) без бизнес-логики
```

### Шаг 3: Найди примеры в проекте

Используй `find` для поиска похожих тестов:

```bash
# Для Repository
find . -name "*RepositoryImplTest.kt" -path "*/test/*" | head -3

# Для Interactor
find . -name "*InteractorImplTest.kt" -path "*/test/*" | head -3

# Для UseCase
find . -name "*UseCaseTest.kt" -path "*/test/*" | head -3

# Для ViewModel
find . -name "*ViewModelBaseTest.kt" -path "*/test/*" | head -3
```

Прочитай 1-2 примера для понимания паттернов проекта.

### Шаг 4: Определи путь файла теста

**ВАЖНО:** Тестовый файл должен быть в ТОМ ЖЕ пакете что исходный класс!

```bash
# Исходный класс:
src/main/java/kz/berekebank/business/core/push/push_impl/data/repositories/PushRepository.kt

# Путь теста (пакет одинаковый!):
src/test/kotlin/kz/berekebank/business/core/push/push_impl/data/repositories/PushRepositoryTest.kt

# Извлеки пакет из исходного файла и используй его в тесте:
package kz.berekebank.business.core.push.push_impl.data.repositories
```

### Шаг 5: Генерация теста

Создай тест со следующей структурой:

#### Обязательные элементы:

**1. Imports:**
```kotlin
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.DisplayName
import com.google.common.truth.Truth.assertThat
import io.mockk.*
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import kz.berekebank.business.core.utils.testing.FlowTestUtils
```

**2. Структура класса:**
```kotlin
@ExperimentalCoroutinesApi
class {ClassName}Test {

    // Моки с префиксом mock
    private val mockDependency: Dependency = mockk(relaxed = true)
    private lateinit var classUnderTest: ClassName

    @BeforeEach
    fun setUp() {
        classUnderTest = ClassName(mockDependency)
    }

    @AfterEach
    fun tearDown() {
        unmockkAll()
        clearAllMocks()
        FlowTestUtils.cleanupFlowResources()
    }

    // Тесты...
}
```

**3. Структура теста Given-When-Then:**
```kotlin
@DisplayName("When {condition} - Then {expected result}")
@Test
fun methodName_condition_result() = runTest {
    // Given: подготовка данных и моков
    val mockData = mockk<Data>(relaxed = true)
    coEvery { mockRepository.getData() } returns RequestResult.Success(mockData)

    // When: выполнение тестируемого действия
    val result = classUnderTest.execute()

    // Then: проверка результатов
    assertThat(result).isInstanceOf(RequestResult.Success::class.java)
    coVerify { mockRepository.getData() }
}
```

### Шаг 6: Критические правила

✅ **ОБЯЗАТЕЛЬНО:**
- @DisplayName для каждого теста (без backticks!)
- Given-When-Then с комментариями
- Truth assertions (`assertThat`)
- Prefix `mock` для всех моков
- `FlowTestUtils.coVerifyFlowCall` для Flow методов
- `FlowTestUtils.cleanupFlowResources()` в tearDown
- **Максимальная длина строки: 80 символов** (требование detekt)

❌ **ЗАПРЕЩЕНО:**
- Backticks в именах методов
- JUnit assertions (assertEquals, assertTrue)
- Thread.sleep()
- Обычный coVerify для Flow
- Строки длинней 80 символов

### Шаг 7: Покрытие

Сгенерируй тесты для:
- ✅ Happy path (успешный сценарий)
- ✅ Error handling (обработка ошибок)
- ✅ Edge cases (null, empty, большие значения)
- ✅ Все публичные методы (и только публичные!)

### Шаг 8: Специфика по слоям

**UseCase:**
```kotlin
@DisplayName("When execute with valid input - Then returns Success")
@Test
fun executeValidInput_returnsSuccess() = runTest {
    // Given
    val input = "validInput"
    val expected = mockk<Output>()
    coEvery { mockRepository.process(input) } returns RequestResult.Success(expected)

    // When
    val result = useCase.execute(input)

    // Then
    assertThat(result).isInstanceOf(RequestResult.Success::class.java)
    coVerify { mockRepository.process(input) }
}
```

**Repository (с Flow):**
```kotlin
@DisplayName("When getData called - Then return Flow with DataState Success")
@Test
fun getData_returnsFlowWithSuccess() = runTest {
    // Given
    val mockedDto = mockk<DTO>(relaxed = true)
    val mockedModel = mockk<Model>(relaxed = true)

    mockkStatic("com.example.MapperKt") {
        coEvery { mockedDto.toModel() } returns mockedModel
        coEvery { mockApi.getData() } returns Response.success(mockedDto)

        // When & Then
        repository.getData().test {
            assertThat(awaitItem()).isInstanceOf(DataState.Loading::class.java)
            val success = awaitItem()
            assertThat(success).isInstanceOf(DataState.Success::class.java)
            awaitComplete()
        }

        FlowTestUtils.coVerifyFlowCall { repository.getData() }
    }
}
```

**Repository (с Flow<PagingData> через Turbine):**
```kotlin
import app.cash.turbine.test

@DisplayName("When search query provided - Then returns PagingData Flow")
@Test
fun searchDocuments_validQuery_returnsPagingDataFlow() = runTest {
    // Given
    val query = "test query"
    val mockPagingSource = mockk<PagingSource<Int, Document>>()

    coEvery {
        mockApi.searchDocuments(query)
    } returns flow {
        emit(PagingData.from(listOf(mockk<Document>())))
    }

    // When
    val flow = repository.searchDocuments(query)

    // Then
    flow.test {
        val pagingData = awaitItem()
        assertThat(pagingData).isNotNull()
        cancelAndIgnoreRemainingEvents()
    }

    // Верификация через FlowTestUtils
    FlowTestUtils.coVerifyFlowCall { repository.searchDocuments(query) }
}
```

**ViewModel (создай BaseTest если сложный):**
```kotlin
// BaseTest для сложных ViewModel
@ExperimentalCoroutinesApi
internal abstract class MyViewModelBaseTest {
    protected lateinit var testDispatcher: TestDispatcher
    protected val mockInteractor: Interactor = mockk(relaxed = true)
    protected lateinit var viewModel: MyViewModel

    @BeforeEach
    fun setup() {
        testDispatcher = StandardTestDispatcher()
        Dispatchers.setMain(testDispatcher)
    }

    @AfterEach
    fun tearDown() {
        Dispatchers.resetMain()
        testDispatcher.scheduler.runCurrent()
        unmockkAll()
        clearAllMocks()
        FlowTestUtils.cleanupFlowResources()
    }

    protected fun initViewModel() {
        viewModel = MyViewModel(mockInteractor, testDispatcher)
    }
}
```

### Шаг 9: Валидация

Перед завершением проверь по чек-листу:
- [ ] @DisplayName присутствует (без backticks)
- [ ] Given-When-Then структура
- [ ] FlowTestUtils используется где нужно
- [ ] Все зависимости замоканы с префиксом mock
- [ ] tearDown с FlowTestUtils.cleanupFlowResources()
- [ ] Truth assertions
- [ ] Пакет теста совпадает с пакетом исходного класса ✅
- [ ] Максимум 80 символов на строку (detekt requirement)

### Шаг 10: Проверка качества

После генерации выполни:
1. **Проверка синтаксиса:**
   ```bash
   ./gradlew :module:compileDebugUnitTestKotlin
   ```

2. **Проверка линтера:**
   ```bash
   ./gradlew :module:lintDebugUnitTest
   ```
   Удали any unused imports если найдены.

3. **Запуск тестов:**
   ```bash
   ./gradlew :module:testDebugUnitTest
   ```

### Шаг 11: Проверка покрытия по классу

После успешного запуска тестов выведи процент покрытия конкретного класса:

```bash
# Генерируем XML отчет покрытия
./gradlew :module:koverXmlReport

# Парсим покрытие конкретного класса
CLASS_PATH="path/to/ClassName"  # Пример: kz/berekebank/business/core/push/push_impl/data/repositories/PushRepository

# Извлекаем линии и инструкции из XML
COVERAGE_FILE="build/reports/kover/report.xml"
grep "class name=\"$CLASS_PATH\"" "$COVERAGE_FILE" -A 5 | \
  grep -E "counter type=\"(INSTRUCTION|LINE)\"" | \
  head -2
```

Выведи в формате:
```
📊 Покрытие класса ClassName:
- LINE coverage: XX.X%
- INSTRUCTION coverage: XX.X%
```

Примеры интерпретации:
- ✅ > 80% - Отличное покрытие
- ⚠️  60-80% - Хорошее, но можно улучшить
- ❌ < 60% - Требуется дополнительные тесты

## Output

Выведи в следующем порядке:

1. **Заголовок с именем класса:**
   ```
   ✅ Создан тест: ClassName
   ```

2. **Путь к файлу теста:**
   ```
   📍 Файл: src/test/kotlin/kz/berekebank/business/core/push/.../ClassName Test.kt
   ```

3. **Статистика:**
   ```
   📊 Статистика:
   - Всего тестов: N
   - Happy path: N
   - Error cases: N
   - Edge cases: N
   ```

4. **Покрытие класса (ОБЯЗАТЕЛЬНО):**
   ```
   📈 Покрытие ClassName:
   - LINE coverage: XX.X%
   - INSTRUCTION coverage: XX.X%
   ```

5. **Список методов:**
   ```
   ✅ Тестируемые методы:
   1. methodName1() - happy path + error case
   2. methodName2() - happy path + edge case
   ...
   ```

6. **Примененные стандарты:**
   ```
   ✅ Стандарты:
   - @DisplayName ✅
   - Given-When-Then ✅
   - Truth assertions ✅
   - FlowTestUtils ✅
   ```

7. **Рекомендации:**
   ```
   💡 Рекомендации:
   - Дополнительный тест-кейс 1
   - Дополнительный тест-кейс 2
   ```

## Пример использования

```bash
/generate-test feature/auth/domain/LoginUseCase.kt
/generate-test feature/documents/data/DocumentsRepositoryImpl.kt
/generate-test core/push/push-impl/src/main/java/kz/berekebank/business/core/push/push_impl/data/repositories/PushRepository.kt
```

## Ключевые улучшения

✅ Явная инструкция о пакетах тестов
✅ Пакет теста = пакет исходного класса
✅ Проверка качества после генерации (синтаксис, линтер, тесты)
