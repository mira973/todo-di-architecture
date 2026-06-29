from app.users.interfaces import UserRepoABC


class UserRepo(UserRepoABC):
    def __init__(self):
        self.users = []
        self.counter = 1

    def add(self, name: str) -> dict:
        user = {"id": self.counter, "name": name}
        self.users.append(user)
        self.counter += 1
        return user

    def get_all(self) -> list[dict]:
        return self.users

    def exists(self, user_id: int) -> bool:
        return any(user["id"] == user_id for user in self.users)
