def check_win(emoji: str, outcome: str, value: int) -> tuple[bool, float]:
    if emoji == "🎲":
        if outcome in {"Четное", "Нечетное", "Больше 3", "Меньше 4"}:
            if outcome == "Четное":
                return (value % 2 == 0, 1.9)
            if outcome == "Нечетное":
                return (value % 2 != 0, 1.9)
            if outcome == "Больше 3":
                return (value > 3, 1.9)
            if outcome == "Меньше 4":
                return (value < 4, 1.9)

        if outcome.startswith("Число "):
            target = int(outcome.split()[-1])
            return (value == target, 5.0)

    elif emoji == "🎯":
        if outcome == "Яблочко":
            return (value == 6, 5.0)
        if outcome == "Мимо":
            return (value == 1, 3.0)
        if outcome == "Красное":
            return (value in {2, 4}, 1.9)
        if outcome == "Белое":
            return (value in {3, 5}, 1.9)

    elif emoji == "🎰":
        if outcome == "Три семерки (777)":
            return (value == 64, 15.0)

        v = value - 1
        r1 = v % 4
        r2 = (v // 4) % 4
        r3 = (v // 16) % 4

        if outcome == "Любые 3 в ряд":
            return (r1 == r2 == r3, 5.0)
        if outcome == "2 подряд одинаковых":
            return ((r1 == r2) or (r2 == r3), 1.9)

    elif emoji == "🏀":
        if outcome == "Попал":
            return (value in {4, 5}, 1.8)
        if outcome == "Не попал":
            return (value in {1, 2}, 1.8)
        if outcome == "Застрянет":
            return (value == 3, 5.0)

    elif emoji == "⚽":
        if outcome == "Попал":
            return (value in {3, 4, 5}, 1.5)
        if outcome == "Не попал":
            return (value == 1, 2.5)
        if outcome == "От штанги":
            return (value == 2, 2.5)
        if outcome == "Девятка":
            return (value == 4, 2.5)

    elif emoji == "🎳":
        if outcome == "Страйк":
            return (value == 6, 4.0)
        if outcome == "Не попал":
            return (value == 1, 3.0)
        if outcome == "Сбито 1 кегля":
            return (value == 2, 3.0)
        if outcome == "Сбито 3 кегли":
            return (value == 3, 3.0)
        if outcome == "Сбито 4 кегли":
            return (value == 4, 3.0)
        if outcome == "Сбито 5 кеглей":
            return (value == 5, 3.0)

    return (False, 0.0)
