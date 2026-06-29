class UserService:
    def __init__(self, repo):
        self.repo = repo

    def create_user(self, name: str):
        return self.repo.add(name)

    def get_users(self):
        return self.repo.get_all()