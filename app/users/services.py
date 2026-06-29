from app.users.interfaces import UserRepoABC, UserServiceABC


class UserService(UserServiceABC):
    repo: UserRepoABC

    def create_user(self, name: str) -> dict:
        return self.repo.add(name)

    def get_users(self) -> list[dict]:
        return self.repo.get_all()

    def user_exists(self, user_id: int) -> bool:
        return self.repo.exists(user_id)
