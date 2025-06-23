# app/registry.py
import pkgutil
import importlib
import logging
import os

def auto_register_modules(mcp, package_name: str):
    """
    指定パッケージ（例："app.tools"）内の全モジュールを走査し、
    モジュール内に register 関数が定義されていればそれを実行する。
    """
    try:
        package = importlib.import_module(package_name)
    except ModuleNotFoundError:
        # ディレクトリが存在しない場合は静かにスキップ
        # これはオプショナルな機能（entries, resources等）のため正常な動作
        package_path = package_name.replace('.', '/')
        if not os.path.exists(package_path):
            logging.debug(f"オプショナルパッケージ {package_name} はスキップされました（ディレクトリが存在しません）")
        else:
            logging.debug(f"パッケージ {package_name} のインポートをスキップしました")
        return
    except Exception as e:
        # その他のエラーは警告として記録
        logging.warning(f"パッケージ {package_name} のインポートに失敗しました: {e}")
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