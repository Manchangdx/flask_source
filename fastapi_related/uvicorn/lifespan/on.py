import asyncio
import logging
import click
from asyncio import Queue
from typing import Union

from asgiref.typing import (
    LifespanScope,
    LifespanShutdownCompleteEvent,
    LifespanShutdownEvent,
    LifespanShutdownFailedEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupEvent,
    LifespanStartupFailedEvent,
)

from uvicorn import Config

LifespanReceiveMessage = Union[LifespanStartupEvent, LifespanShutdownEvent]
LifespanSendMessage = Union[
    LifespanStartupFailedEvent,
    LifespanShutdownFailedEvent,
    LifespanStartupCompleteEvent,
    LifespanShutdownCompleteEvent,
]

STATE_TRANSITION_ERROR = "Got invalid state transition on lifespan protocol."


class LifespanOn:
    def __init__(self, config: Config) -> None:
        if not config.loaded:
            config.load()

        self.config = config
        self.logger = logging.getLogger("uvicorn.error")
        self.startup_event = asyncio.Event()
        self.shutdown_event = asyncio.Event()
        self.receive_queue: "Queue[LifespanReceiveMessage]" = asyncio.Queue()
        self.error_occured = False
        self.startup_failed = False
        self.shutdown_failed = False
        self.should_exit = False

    async def startup(self) -> None:
        """启动程序
        """
        #self.logger.info("Waiting for application startup.")
        cs = click.style('>>>>>> 开始准备工作 <<<<<<', fg='black')
        print(f'【uvicorn.lifespan.on.LifespanOn.startup】{cs}')

        loop = asyncio.get_event_loop()
        # 给事件循环添加任务
        main_lifespan_task = loop.create_task(self.main())  # noqa: F841
        # Keep a hard reference to prevent garbage collection
        # See https://github.com/encode/uvicorn/pull/972
        startup_event: LifespanStartupEvent = {"type": "lifespan.startup"}
        await self.receive_queue.put(startup_event)
        # 启动事件循环，也就是执行 self.main() 这个协程
        await self.startup_event.wait()

        if self.startup_failed or (self.error_occured and self.config.lifespan == "on"):
            self.logger.error("Application startup failed. Exiting.")
            self.should_exit = True
        else:
            cs = click.style('>>>>>> 准备工作完毕 <<<<<<', fg='black')
            print(f'【uvicorn.lifespan.on.LifespanOn.startup】{cs}')
            #self.logger.info("Application startup complete.")

    async def shutdown(self) -> None:
        if self.error_occured:
            return
        #self.logger.info("Waiting for application shutdown.")
        print('【uvicorn.lifespan.on.LifespanOn.shutdown】Shutting down application')
        shutdown_event: LifespanShutdownEvent = {"type": "lifespan.shutdown"}
        await self.receive_queue.put(shutdown_event)
        await self.shutdown_event.wait()

        if self.shutdown_failed or (
            self.error_occured and self.config.lifespan == "on"
        ):
            self.logger.error("Application shutdown failed. Exiting.")
            self.should_exit = True
        else:
            self.logger.info("Application shutdown complete.")

    async def main(self) -> None:
        try:
            # 下面这个 app 可能是 uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware 类的实例
            # 它创建于 uvicorn.config.Config.load 方法中
            app = self.config.loaded_app
            print('【uvicorn.lifespan.on.LifespanOn.main】app:', app)
            scope: LifespanScope = {
                "type": "lifespan",
                "asgi": {"version": self.config.asgi_version, "spec_version": "2.0"},
            }
            await app(scope, self.receive, self.send)
        except BaseException as exc:
            self.asgi = None
            self.error_occured = True
            if self.startup_failed or self.shutdown_failed:
                return
            if self.config.lifespan == "auto":
                msg = "ASGI 'lifespan' protocol appears unsupported."
                self.logger.info(msg)
            else:
                msg = "Exception in 'lifespan' protocol\n"
                self.logger.error(msg, exc_info=exc)
        finally:
            self.startup_event.set()
            self.shutdown_event.set()

    async def send(self, message: LifespanSendMessage) -> None:
        print(f"【uvicorn.lifespan.on.LifespanOn.send】message['type']: {message['type']}")
        assert message["type"] in (
            "lifespan.startup.complete",
            "lifespan.startup.failed",
            "lifespan.shutdown.complete",
            "lifespan.shutdown.failed",
        )

        # 处理请求成功
        if message["type"] == "lifespan.startup.complete":
            assert not self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.startup_event.set()

        # 处理请求失败
        elif message["type"] == "lifespan.startup.failed":
            assert not self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.startup_event.set()
            self.startup_failed = True
            if message.get("message"):
                self.logger.error(message["message"])

        # 处理响应成功
        elif message["type"] == "lifespan.shutdown.complete":
            print('okk')
            assert self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.shutdown_event.set()

        # 处理响应失败
        elif message["type"] == "lifespan.shutdown.failed":
            assert self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.shutdown_event.set()
            self.shutdown_failed = True
            if message.get("message"):
                self.logger.error(message["message"])

    async def receive(self) -> LifespanReceiveMessage:
        # TODO 此处调用的是 asyncio.queues.Queue.get 方法，需进一步了解
        return await self.receive_queue.get()
