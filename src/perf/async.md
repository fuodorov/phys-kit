# Асинхронность

Сколько бы потоков ты ни запустил, GIL пропускает через интерпретатор только один из них, а заводить больше одновременно считающих процессов, чем ядер, смысла нет.

Есть класс задач, где процессор ни при чём. Программа, скачивающая тысячу файлов или опрашивающая сотню приборов по сети, почти всё время **ждёт**. Запрос, отправленный по сети, ушёл, ответ не пришёл, делать нечего. Держать под каждое такое ожидание отдельный поток расточительно, поскольку поток, отданный под простой, стоит памяти и переключений контекста, а полезной работы не делает.

Асинхронность поручает одному потоку тысячу ожиданий сразу: пока один запрос ждёт ответа, выполняется другой. Механику обеспечивают генераторы и корутины, разобранные в главе [«Итераторы, генераторы и корутины»](../dev/python/async.md): планировщику нужна функция, умеющая приостановиться и продолжить с того же места.

## Работа с разными типами задач

Долгое время на природу нагрузки внутри программы можно было не смотреть, поскольку приложения писали большими и монолитными, а проблемы с производительностью решали грубой силой: добавленными потоками, лишними процессами или ещё одной машиной, купленной в стойку.

Сегодня одних процессов и потоков не хватает, и выбор инструмента начинается с вопроса, чем занята программа. Задачи делят на три типа:

- **CPU bound-задачи.** Задачи, требующие интенсивного использования процессора, среди которых сложные математические модели, обучение нейронных сетей, рендеринг графики и вычисление хешей.

- **I/O bound-задачи (non-RAM I/O bound).** Задачи, в которых основная часть работы приходится на ввод/вывод информации *I/O* или *input/output*, относящиеся в основном к работе с файловой системой и с сетью. 

- **Memory bound-задачи (RAM I/O bound).** Задачи с интенсивной работой по оперативной памяти, появляющиеся, как правило, в сложных математических моделях. Из-за медленной работы с оперативной памятью всё больше моделей обрабатывают на видеокартах, устроенных по-другому. Другим примером служит обработка огромного объёма данных в *Map-Reduce*-системах, например таких как *Spark*, идущая тем быстрее, чем больше оперативной памяти.

Подробнее об этом рассказано в англоязычных статьях [о значении терминов CPU bound и I/O bound](https://stackoverflow.com/questions/868568/what-do-the-terms-cpu-bound-and-i-o-bound-mean) и [о производительности](https://link.springer.com/chapter/10.1007/978-1-4842-4932-1_15).

Из-за массового перехода на микросервисы количество сетевого взаимодействия между системами многократно возросло, а вместе с ним и нагрузка, приходящаяся на базы данных. Проблемы работы с сетью или с доступом к БД относятся к I/O bound-задачам, сводящимся к ожиданию ответа на запрос, отправленный во внешнюю систему. Такой класс задач в монолитных системах решался пулом потоков, [thread pool](https://en.wikipedia.org/wiki/Thread_pool), которого с ростом сетевой нагрузки между множеством сервисов перестало хватать.

Классический ответ на I/O bound-нагрузку — добавить ресурсов, но докупать серверы вместо того, чтобы разбираться с кодом, способны лишь компании с большими бюджетами. В лаборатории этот путь закрыт, остаётся писать код, рассчитанный на такую нагрузку.

Представь приложение, ходящее на некий сайт-агрегатор за данными по фильмам и складывающее полученное в БД (ссылка на сайт выдуманная):


```python
import requests

def do_some_logic(data):
    pass
  
def save_to_database(data):
    pass

data = requests.get('https://data.aggregator.com/films')
processed_data = do_some_logic(data)
save_to_database(processed_data)
```

Код линейный, и пока запрос один, всё хорошо, но стоит ему обслуживать многих клиентов сразу, и время ответа поплывёт. Бо́льшую часть времени интерпретатор не делает ничего полезного, а ждёт запроса от клиента, ждёт ответа от внешнего сайта, ждёт записи, подтверждённой базой. А клиенты в это время ждут его.

Схема выполнения программы:

![1_1_AsyncAPI_1_1629286149.png](1_1_AsyncAPI_1_1629286149.png)

Тип задачи в каждой ячейке:

![1.1_3_AsyncAPI_1_1629286157.png](1.1_3_AsyncAPI_1_1629286157.png)

Интуитивно кажется, что время распределено между ячейками примерно поровну, но в реальности картина другая:

![1_2_AsyncAPI_2_1629286153.png](1_2_AsyncAPI_2_1629286153.png)

Бо́льшую часть времени программа ждёт ввода/вывода, а полезная работа теряется на этом фоне.
Можно распараллелить код на процессы и потоки. Поможет, но ненадолго: расходы ресурсов сервера вырастут, а число процессов и потоков ограничено, потому что кончится либо оперативная память под потоки, либо ядра под процессы. Добавляется `GIL`, пропускающий через интерпретатор только один поток за раз: массовый параллелизм на потоках он делает бессмысленным и добавляет собственные накладные расходы, пусть и небольшие.

Выполнение программы с потоками:

![S1.1_4_AsyncAPI_1_1629286161.png](S1.1_4_AsyncAPI_1_1629286161.png)

На I/O bound-задачах два потока отрабатывают почти вдвое лучше. Но два потока, полезших в одни и те же данные, дают проблему [«состояния гонок»](https://ru.wikipedia.org/wiki/Состояние_гонки), а многопоточный код требует от разработчика большей внимательности, чем линейный. И наплодить потоков сколько угодно не выйдет: памяти под каждый стек они съедают несравнимо больше, чем корутины.

Интерпретатор по-прежнему бо́льшую часть времени ничего не делает, а лишь спрашивает у операционной системы, завершилась ли операция ввода-вывода, запущенная минуту назад. Процессы и потоки этого не меняют. Простаивать будет каждый из них, зато добавятся накладные расходы на переключение контекста и на память, выделенную под стеки, отчего положение может даже ухудшиться.


Выход не в том, чтобы плодить исполнителей, а в том, чтобы научить одного не простаивать. Этим занимается асинхронный код.

## Event-loop

Цикл событий — сердце асинхронных программ в Python. Разберём простую реализацию, предложенную Дэвидом Бизли (David Beazley) [в 2009 году](https://web.archive.org/web/20250108084634/http://www.dabeaz.com/coroutines/Coroutines.pdf): в ней нет конструкций, которыми с тех пор обросли настоящие реализации, и устройство видно насквозь. [Код Бизли](https://web.archive.org/web/20240119054015/http://www.dabeaz.com/coroutines/pyos8.py) приведён к современной версии Python.

Архитектура цикла событий:

![1_Event_Loop_1629282397.png](1_Event_Loop_1629282397.png)

Рассмотрим блоки:

- **Планировщик (Scheduler)**. Корень всей программы. Обрабатывает задачи, собранные в очереди, и следит за их правильным переключением между собой.
- **Очередь задач (Task queue)**. Здесь копятся новые задачи, поставленные на исполнение.
- **Задача (Task)**. Основной блок работы цикла событий. В задачах хранится информация о выполняемой корутине. Умеет обрабатывать цепочку вложенных корутин.
- **Корутина (Coroutine)**. Исполняемый код, которым оперирует планировщик задач.
- **Системный вызов (SystemCall)**. Блоки кода, расширяющие функциональность планировщика.
- **Корутина для выполнения работы с I/O (I/O-tasks)**. В планировщик добавляется специальная задача (Task), предназначенная для обработки I/O-событий от ОС.
- **Селектор (Selector)**. Он слушает события от ОС и передаёт работу корутинам, ждущим обработки I/O-сообщений.

Планировщик принимает задачи и справедливо обрабатывает накопленный список.


```python
from __future__ import annotations

import logging
from typing import Generator
from queue import Queue


class Scheduler:
    def __init__(self):
        self.ready = Queue()
        self.task_map = {}

    def add_task(self, coroutine: Generator) -> int:
        new_task = Task(coroutine)
        self.task_map[new_task.tid] = new_task
        self.schedule(new_task)
        return new_task.tid

    def exit(self, task: Task):
        del self.task_map[task.tid]

    def schedule(self, task: Task):
        self.ready.put(task)

    def _run_once(self):
        task = self.ready.get()
        try:
            result = task.run()
        except StopIteration:
            self.exit(task)
            return
        self.schedule(task)

    def event_loop(self):
        while self.task_map:
            self._run_once()
```


Вся работа происходит в функции `event_loop()`, достающей задачи одну за другой. В функции `_run_once()` идёт обработка одной итерации цикла событий, где поочерёдно берутся и запускаются задачи, поставленные в очередь. Если задача не завершилась, то она возвращается в очередь `self.ready`. Выполненные задачи убирает из планировщика функция `exit()`.

Задачу добавляет функция `add_task()`: принимает корутину и создаёт с ней задачу в планировщике. Уже созданную задачу ставит в планировщик функция `schedule()`.

Устройство задачи:


```python
import types
from typing import Generator, Union

class Task:
    task_id = 0

    def __init__(self, target: Generator):
        Task.task_id += 1
        self.tid = Task.task_id  # Task ID
        self.target = target  # Target coroutine
        self.sendval = None  # Value to send
        self.stack = []  # Call stack

    # Run a task until it hits the next yield statement
    def run(self):
        while True:
            try:
                result = self.target.send(self.sendval)

                if isinstance(result, types.GeneratorType):
                    self.stack.append(self.target)
                    self.sendval = None
                    self.target = result
                else:
                    if not self.stack:
                        return
                    self.sendval = result
                    self.target = self.stack.pop()

            except StopIteration:
                if not self.stack:
                    raise
                self.sendval = None
                self.target = self.stack.pop()
```

Задача — обёртка вокруг корутины. У каждой задачи есть свой `id`, учитываемый в планировщике в словаре `task_map`. На его заполненность смотрит планировщик при выполнении поставленных задач.

Задача выполняет корутины методом `run()`. Пусть есть корутина, вызывающая другую корутину, а та вызывает третью:


```python
def square(x):
    yield x * x

def add(x, y):
    yield from square(x + y)

def main():
    result = yield add(1, 2)
    print(result)
    yield
```

Это слегка изменённый [код Бизли](https://web.archive.org/web/20240119054021/http://www.dabeaz.com/coroutines/trampoline.py) из его выступления. Выполним эту цепочку корутин внутри `Task`.


```python
task = Task(main())
task.run()
```

    9


Так же выполнятся и остальные корутины, вложенные в цепочку. Осталось научить планировщик работать с вводом-выводом.

Для этого ему понадобится селектор, обёртка над механизмом операционной системы, умеющим ждать событий сразу на многих файловых дескрипторах, зарегистрированных программой.


```python
import logging
from typing import Generator, Union
from queue import Queue
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE


logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self.ready = Queue()
        self.selector = DefaultSelector()
        self.task_map = {}

    def add_task(self, coroutine: Generator) -> int:
        new_task = Task(coroutine)
        self.task_map[new_task.tid] = new_task
        self.schedule(new_task)
        return new_task.tid

    def exit(self, task: Task):
        logger.info('Task %d terminated', task.tid)
        del self.task_map[task.tid]

    # I/O waiting
    def wait_for_read(self, task: Task, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            self.selector.register(fd, EVENT_READ, (task, None))

        else:
            mask, (reader, writer) = key.events, key.data
            self.selector.modify(fd, mask | EVENT_READ, (task, writer))

    def wait_for_write(self, task: Task, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            self.selector.register(fd, EVENT_WRITE, (None, task))

        else:
            mask, (reader, writer) = key.events, key.data
            self.selector.modify(fd, mask | EVENT_WRITE, (reader, task))

    def _remove_reader(self, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            pass
        else:
            mask, (reader, writer) = key.events, key.data
            mask &= ~EVENT_READ
            if not mask:
                self.selector.unregister(fd)
            else:
                self.selector.modify(fd, mask, (None, writer))

    def _remove_writer(self, fd: int):
        try:
            key = self.selector.get_key(fd)
        except KeyError:
            pass
        else:
            mask, (reader, writer) = key.events, key.data
            mask &= ~EVENT_WRITE
            if not mask:
                self.selector.unregister(fd)
            else:
                self.selector.modify(fd, mask, (reader, None))

    def io_poll(self, timeout: Union[None, float]):
        events = self.selector.select(timeout)
        for key, mask in events:
            fileobj, (reader, writer) = key.fileobj, key.data
            if mask & EVENT_READ and reader is not None:
                self.schedule(reader)
                self._remove_reader(fileobj)
            if mask & EVENT_WRITE and writer is not None:
                self.schedule(writer)
                self._remove_writer(fileobj)

    def io_task(self) -> Generator:
        while True:
            if self.ready.empty():
                self.io_poll(None)
            else:
                self.io_poll(0)
            yield

    def schedule(self, task: Task):
        self.ready.put(task)

    def _run_once(self):
        task = self.ready.get()
        try:
            result = task.run()
        except StopIteration:
            self.exit(task)
            return
        self.schedule(task)

    def event_loop(self):
        self.add_task(self.io_task())
        while self.task_map:
            self._run_once()
```

Перед стартом цикла событий планировщик заводит одну особую, бесконечную задачу `io_task`. Её вечный цикл забирает у селектора накопившиеся события и тут же отдаёт управление обратно планировщику.

Если очередь задач пуста, селектор ждёт событий без таймаута, до появления новых. Иначе таймаут 0, чтобы сразу забрать все события, накопленные операционной системой.

Пришедшие из селектора события обрабатываем и убираем отработанные файловые дескрипторы. Одна и та же задача может ожидать присланных данных и одновременно пытаться записать свои, поэтому в поле `data` хранится кортеж `(reader, writer)`.

`event_loop` предоставляет интерфейс для работы с сокетами, четыре метода:
- `wait_for_read`,
- `wait_for_write`,
- `_remove_reader`,
- `_remove_writer`.

Эти методы позволяют работать с циклом событий, встроенным в ОС.

Основное назначение цикла событий — переключение корутин, а ходят ли те по сети, лезут ли на диск или ничего не ждут, ему безразлично.

Осталась конструкция `SystemCall`. Цикл событий напоминает работу ОС, и механизм прерываний, передающий управление наверх, позаимствован у неё: в асинхронном коде прерывание обеспечивает `yield`. После переключения контекста может вызываться системная функция, заказанная корутиной. Например, для создания новых задач:


```python
class SystemCall:
    def handle(self, sched: Scheduler, task: Task):
        pass


class NewTask(SystemCall):
    def __init__(self, target: Generator):
        self.target = target

    def handle(self, sched: Scheduler, task: Task):
        tid = sched.add_task(self.target)
        task.sendval = tid
        sched.schedule(task)
```

В `Scheduler` добавляется фрагмент:


```python
class Scheduler:
    ...
    def _run_once(self):
        task = self.ready.get()
        try:
            result = task.run()
            if isinstance(result, SystemCall):
                result.handle(self, task)
                return
        except StopIteration:
            self.exit(task)
            return
        self.schedule(task)
```

А в `Task` — условие при выполнении корутин:


```python
import types
from typing import Generator, Union

class Task:
    ...
    def run(self):
        while True:
            try:
                result = self.target.send(self.sendval)
                if isinstance(result, SystemCall):
                    return result
                ...
```


`NewTask` предоставляет интерфейс для создания новых задач в цикле событий и абстрагирует клиентский код. Это эмуляция защищённой среды ОС, предоставляющей безопасные методы для работы с ядром, чтобы клиентский код не мешал другим программам, запущенным в системе. Таким же образом можно сделать `KillTask` или `WaitTask`.

Последняя проблема — блокирующие операции. Пока запущенная операция не вернётся, цикл событий стоит вместе с ней. Лечится это на уровне сокетов: вызов `socket.setblocking(False)` переводит сокет в неблокирующий режим, и вместо ожидания он немедленно сообщает, что данных пока нет. Ждать их будет селектор, сразу за всех.

## Asyncio

`asyncio` — основная встроенная библиотека для асинхронного программирования.

С версии Python 3.5 в языке есть синтаксис async/await. Он даёт «нативные» корутины — отдельную сущность языка, а не переиспользованный генератор. Благодаря разделению появились асинхронные генераторы, и асинхронный код стал работать быстрее.


Простая программа с async/await:


```python
import random
import asyncio


async def func():
    r = random.random()
    await asyncio.sleep(r)
    return r


async def value():
    result = await func()
    print(result)


if __name__ == '__main__':
    asyncio.run(value())
```

Функция `asyncio.run` заводит планировщик задач, устроенный по разобранным выше принципам, и закрывает его по завершении. Переключением между корутинами заведует `await`.

Основные функции `asyncio`:

- `gather` выполняет переданный список корутин одновременно и дожидается результатов от всех.
- `sleep` заставляет корутину уснуть на определённое количество секунд.
- `wait`/`wait_for` дожидаются выполнения уже запущенной корутины.

Основные функции `event_loop`:

- `get_event_loop` возвращает цикл событий текущего потока, создавая его при необходимости. В новом коде вместо связки `get_event_loop` и `run_until_complete` пишут одну строку `asyncio.run(...)`.
- `run_until_complete`/`run` запускают и проверяют асинхронные функции.
- `shutdown_asyncgens` правильно завершает выполнение цикла событий и всех корутин; о ней часто забывают.
- `call_soon` ставит обычную функцию (не корутину) в очередь на ближайшую итерацию цикла и не ждёт её выполнения. Так поставленная функция может бесконечно переставлять саму себя.

Ключевое отличие asyncio от предложенной реализации: asyncio работает на функциях обратного вызова, колбэках (callback). Этот механизм распределяет время между задачами справедливее. Каждая корутина встаёт в очередь и дожидается исполнения, тогда как в простом планировщике переключения не произойдёт, пока вся цепочка корутин не выполнится, а остальные задачи, поставленные в очередь, всё это время стоят. Недостаток колбэков — callback hell, когда после вызова каждой функции нужно вызвать ещё одну функцию и ещё одну:


```python
func1.add_callback(
    func2.add_callback(
                func3.add_callback(func4)
        )
) 
```


Синтаксис async/await позволяет этого избежать.


```python
await func4()
await func3()
await func2()
await func1() 
```


Это возможно благодаря классу `Future`, прячущему колбэки и делающему код линейным. Создавать `Future` руками в современном коде почти не приходится: это делают `create_task` и `gather`.

## Асинхронные фреймворки

Поверх `asyncio` (а иногда и мимо него) выросла экосистема. Физику она нужна, когда вокруг готового расчёта надо построить сервис: принимать данные с прибора, отдавать результаты коллегам, ходить в базу лаборатории. Три характерных представителя.

### Twisted

Один из старейших асинхронных фреймворков, построенный на собственной реализации event-loop.

**Основные концепции:**

1. **Protocol**, описание получения и отправки данных
2. **Factory**, управление созданием объектов протокола
3. **Reactor**, собственная реализация event-loop
4. **Deferred-объекты**, цепочки обратных вызовов

**Пример Deferred-объекта:**

```python
from twisted.internet import defer

def toint(data):
    return int(data)

def increment_number(data):
    return data + 1

def print_result(data):
    print(data)

def handleFailure(f):
    print("OOPS!")

def get_deferred():
    d = defer.Deferred()
    return d.addCallbacks(toint, handleFailure)\
           .addCallbacks(increment_number, handleFailure)\
           .addCallback(print_result)
```

### Aiohttp

Асинхронные HTTP-клиент и сервер, построенные поверх asyncio.

**Пример приложения:**

```python
import aiohttp
from aiohttp import web

async def get_phrase():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://fish-text.ru/get', 
                             params={'type': 'title'}) as response:
            result = await response.json(content_type='text/html; charset=utf-8')
            return result.get('text')

async def index_handler(request):
    return web.Response(text=await get_phrase())

async def response_signal(request, response):
    response.text = response.text.upper()
    return response

async def make_app():
    app = web.Application()
    app.on_response_prepare.append(response_signal)
    app.add_routes([web.get('/', index_handler)])
    return app

web.run_app(make_app())
```

### FastAPI

Современный фреймворк для быстрой разработки API, построенный на Starlette и Pydantic.

**Простой пример API:**

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(title="Простые математические операции")

class Add(BaseModel):
    first_number: int = Field(title='Первое слагаемое')
    second_number: Optional[int] = Field(None, title='Второе слагаемое')

class Result(BaseModel):
    result: int = Field(title='Результат')

@app.post("/add", response_model=Result)
async def create_item(item: Add):
    return {
        'result': item.first_number + (item.second_number or 1)
    }
```

## Резюме

Асинхронность — не универсальный ускоритель, а инструмент, заточенный под задачи, где программа ждёт. Для расчётов она бесполезна. Одна корутина, занявшая процессор надолго, остановит весь цикл событий вместе с очередью, собранной к этому моменту: поток по-прежнему один.

Ориентируйся так:

* **задача ждёт сеть, диск или прибор**, тогда бери асинхронность, выигрыш может быть в десятки раз;
* **задача считает**, тогда бери процессы (`multiprocessing`), векторизацию NumPy или компиляцию, разобранные в предыдущих главах;
* **и то и другое**, тогда бери цикл событий для ожиданий плюс пул процессов для расчётов через `loop.run_in_executor`.

**В асинхронном коде не должно быть блокирующих вызовов.** Одна `time.sleep()` или синхронный запрос к базе останавливает не свою корутину, а всю программу.
