import inspect
from datetime import datetime, timedelta
import typing
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext


class AiogramTTLCache:
    def __init__(self, **ttl):
        self.ttl = ttl
        self.cache = {}
        self.default = datetime(2000, 1, 1)

    def get(self, *,
            message: types.Message = None,
            chat: typing.Union[str, int] = None,
            user: typing.Union[str, int] = None):
        if message is not None:
            chat, user = message.chat.id, message.from_user.id
        chat, user = self.check_input(chat=chat, user=user)
        ttl = self.cache.get(chat, {}).get(user, self.default)
        if datetime.now() < ttl:
            return True
        self.cache.get(chat, {}).pop(user, None)
        return False

    def set(self, *,
            message: types.Message = None,
            chat: typing.Union[str, int] = None,
            user: typing.Union[str, int] = None, **ttl):
        if message is not None:
            chat, user = message.chat.id, message.from_user.id
        chat, user = self.check_input(chat=chat, user=user)
        delta_ttl = ttl or self.ttl
        if not delta_ttl:
            raise Exception("where ttl?????")
        time = datetime.now() + timedelta(**delta_ttl)
        self.cache.setdefault(chat, {}).setdefault(user, time)

    def left(self, *,
            message: types.Message = None,
            chat: typing.Union[str, int] = None,
            user: typing.Union[str, int] = None) -> timedelta:
        if message is not None:
            chat, user = message.chat.id, message.from_user.id
        chat, user = self.check_input(chat=chat, user=user)
        if self.get(chat=chat, user=user):
            return self.cache.get(chat).get(user) - datetime.now()
        else:
            return timedelta()

    @staticmethod
    def check_input(chat: typing.Union[str, int], user: typing.Union[str, int]):
        if chat is None and user is None:
            raise ValueError('`user` or `chat` parameter is required but no one is provided!')

        if user is None and chat is not None:
            user = chat
        elif user is not None and chat is None:
            chat = user
        return str(chat), str(user)


class MemoryStorageEX(MemoryStorage):
    def __init__(self, ttl_cache: AiogramTTLCache, on_end=None):
        super().__init__()
        self.call = on_end
        self.cache = ttl_cache

    async def set_state(self, *,
                        message: types.Message = None,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        state: typing.AnyStr = None):
        if message is not None:
            chat, user = message.chat.id, message.from_user.id
        chat, user = self.resolve_address(chat=chat, user=user)
        if state is not None:
            self.cache.set(chat=chat, user=user)
        self.data[chat][user]['state'] = state

    async def get_state(self, *,
                        message: types.Message = None,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        default: typing.Optional[str] = None) -> typing.Optional[str]:
        if message is not None:
            chat, user = message.chat.id, message.from_user.id
        chat, user = self.resolve_address(chat=chat, user=user)
        if self.cache.get(chat=chat, user=user):
            return self.data[chat][user]['state']
        elif self.data[chat][user]['state'] is not None:
            if self.call is None:
                return await self.set_state(chat=chat, user=user)
            elif inspect.iscoroutinefunction(self.call):
                return await self.call(chat=chat, user=user, storage=self)
            elif isinstance(self.call, typing.Callable):
                return self.call(chat=chat, user=user, storage=self)


class States(StatesGroup):
    test = State()


async def on_state(storage: MemoryStorageEX, **kwargs):
    print(f"reset {kwargs}")
    await storage.finish(**kwargs)


API_TOKEN = ''
cache = AiogramTTLCache(seconds=5)
Storage = MemoryStorageEX(ttl_cache=cache, on_end=on_state)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=Storage)


@dp.message_handler(commands=["start"])
async def start(message: types.Message, state: FSMContext):
    await States.test.set()
    await message.answer(f"state: test")


@dp.message_handler(commands=["status"], state="*")
async def status(message: types.Message, state: FSMContext):
    c_state = await state.get_state()
    await message.answer(f"status: {c_state}")


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
