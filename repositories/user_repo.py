class UserRepo:
    def __init__(self):
        self.users = []
        self.counter = 1

    def add(self, name: str):
        user = {"id": self.counter, "name": name}
        self.users.append(user)
        self.counter += 1
        return user

    def get_all(self):
        return self.users

    def exists(self, user_id: int):
        return any(u["id"] == user_id for u in self.users)