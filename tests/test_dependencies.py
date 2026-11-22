from app.services.dependencies import parse_dependencies


def _by_name(deps):
    return {d.name: d for d in deps}


def test_requirements_txt_parses_names_versions_and_skips_noise() -> None:
    deps = parse_dependencies(
        {
            "api/requirements.txt": (
                "# comment\nfastapi>=0.110,<1\nuvicorn[standard]==0.30.0 ; python_version>'3.8'\n"
                "-r other.txt\n-e .\nhttps://example.com/x.whl\nrequests @ https://x/y.zip\n\n"
            )
        }
    )
    by = _by_name(deps)
    assert set(by) == {"fastapi", "uvicorn", "requests"}
    assert by["fastapi"].version == ">=0.110,<1"
    assert by["uvicorn"].version == "==0.30.0"
    assert by["requests"].version is None
    assert all(d.ecosystem == "PyPI" and d.kind == "runtime" for d in deps)


def test_dev_requirements_file_is_marked_dev() -> None:
    deps = parse_dependencies({"requirements-dev.txt": "pytest==8.0\n"})
    assert deps[0].kind == "dev"


def test_pyproject_pep621_poetry_and_groups() -> None:
    pyproject = (
        '[project]\ndependencies = ["fastapi>=0.1", "pydantic"]\n'
        '[project.optional-dependencies]\ndev = ["pytest"]\nredis = ["redis>=5"]\n'
        '[tool.poetry.dependencies]\npython = "^3.12"\nhttpx = {version = "^0.27"}\n'
    )
    by = _by_name(parse_dependencies({"pyproject.toml": pyproject}))
    assert by["fastapi"].kind == "runtime"
    assert by["pytest"].kind == "dev"
    assert by["redis"].kind == "optional"
    assert by["httpx"].version == "^0.27"
    assert "python" not in by


def test_package_json_kinds() -> None:
    text = (
        '{"dependencies":{"react":"^18"},"devDependencies":{"vite":"^5"},'
        '"peerDependencies":{"react-dom":"^18"}}'
    )
    by = _by_name(parse_dependencies({"web/package.json": text}))
    assert (by["react"].kind, by["vite"].kind, by["react-dom"].kind) == ("runtime", "dev", "optional")
    assert by["react"].ecosystem == "npm" and by["react"].source == "web/package.json"


def test_pubspec_handles_nested_sdk_path_and_dev_blocks() -> None:
    pubspec = (
        "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n  http: ^1.2.0\n"
        "  local_pkg:\n    path: ../local\ndev_dependencies:\n  flutter_test:\n    sdk: flutter\n"
        "  flutter_lints: ^4.0.0 # lints\nflutter:\n  uses-material-design: true\n"
    )
    by = _by_name(parse_dependencies({"client/pubspec.yaml": pubspec}))
    assert by["flutter"].version == "sdk: flutter" and by["flutter"].kind == "runtime"
    assert by["http"].version == "^1.2.0"
    assert by["local_pkg"].version == "path: ../local"
    assert by["flutter_test"].kind == "dev"
    assert by["flutter_lints"].version == "^4.0.0"
    assert "uses-material-design" not in by


def test_cargo_go_and_composer() -> None:
    cargo = '[dependencies]\nserde = "1"\ntokio = { version = "1.38", features = ["full"] }\n[dev-dependencies]\ncriterion = "0.5"\n'
    gomod = "module x\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n\tgolang.org/x/sys v0.1.0 // indirect\n)\nrequire github.com/spf13/cobra v1.8.0\n"
    composer = '{"require":{"php":"^8.2","ext-json":"*","laravel/framework":"^11"},"require-dev":{"phpunit/phpunit":"^11"}}'
    by = _by_name(parse_dependencies({"Cargo.toml": cargo, "go.mod": gomod, "composer.json": composer}))
    assert by["tokio"].version == "1.38" and by["criterion"].kind == "dev"
    assert set(n for n, d in by.items() if d.ecosystem == "Go") == {"github.com/gin-gonic/gin", "github.com/spf13/cobra"}
    assert "php" not in by and "ext-json" not in by
    assert by["phpunit/phpunit"].kind == "dev"


def test_malformed_manifests_never_raise() -> None:
    assert parse_dependencies({"package.json": "{not json", "pyproject.toml": "[[[", "Cargo.toml": "\x00"}) == []


def test_results_are_capped() -> None:
    big = {"package.json": '{"dependencies":{%s}}' % ",".join(f'"p{i}":"1"' for i in range(1000))}
    assert len(parse_dependencies(big)) == 200
