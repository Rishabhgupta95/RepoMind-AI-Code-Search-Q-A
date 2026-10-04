class UserService:

    def authenticate(
        self,
        username,
        password,
    ):
        return True

    def create_user(
        self,
        username,
    ):
        return username


def hello():
    return "hello"