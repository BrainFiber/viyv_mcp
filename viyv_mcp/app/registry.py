# app/registry.py
import pkgutil
import importlib
import logging

def auto_register_modules(mcp, package_name: str):
    """
    指定パッケージ（例："app.tools"）内の全モジュールを走査し、
    モジュール内に register 関数が定義されていればそれを実行する。
    """
    try:
        package = importlib.import_module(package_name)
    except Exception as e:
        logging.error(f"パッケージ {package_name} のインポートに失敗しました: {e}")
        return

    for finder, modname, is_pkg in pkgutil.walk_packages(package.__path__, package_name + "."):
        try:
            module = importlib.import_module(modname)
            if hasattr(module, "register"):
                func = getattr(module, "register")
                if callable(func):
                    func(mcp)
                    logging.info(f"モジュール {modname} を登録しました")
        except Exception as e:
            logging.error(f"モジュール {modname} の登録中にエラーが発生: {e}")