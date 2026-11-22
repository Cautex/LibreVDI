import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packaging", "windows"))
import collect_licenses as cl


def _metadata():
    def pkg(pid, name):
        return {"id": pid, "name": name, "version": "1.0.0", "manifest_path": f"/x/{name}/Cargo.toml"}

    normal = [{"kind": None, "target": None}]
    return {
        "workspace_members": ["app", "tests-helper"],
        "packages": [
            pkg("app", "app"),
            pkg("tests-helper", "tests-helper"),
            pkg("a", "a"),
            pkg("b", "b"),
            pkg("devonly", "devonly"),
            pkg("buildonly", "buildonly"),
            pkg("c", "c"),
        ],
        "resolve": {
            "nodes": [
                {
                    "id": "app",
                    "deps": [
                        {"pkg": "a", "dep_kinds": normal},
                        {"pkg": "devonly", "dep_kinds": [{"kind": "dev", "target": None}]},
                        {"pkg": "buildonly", "dep_kinds": [{"kind": "build", "target": None}]},
                    ],
                },
                {"id": "a", "deps": [{"pkg": "b", "dep_kinds": [{"kind": "dev"}, {"kind": None}]}]},
                {"id": "tests-helper", "deps": [{"pkg": "c", "dep_kinds": normal}]},
            ]
        },
    }


def test_runtime_packages_only_normal_dependencies():
    names = [p["name"] for p in cl.runtime_packages(_metadata())]
    assert names == ["a", "b", "c"]


def test_runtime_packages_restricted_to_roots():
    names = [p["name"] for p in cl.runtime_packages(_metadata(), roots=["app"])]
    assert names == ["a", "b"]


def test_vcpkg_all_ports_skip_build_helpers(tmp_path):
    for triplet, port in (("x64-windows", "ffmpeg"), ("x64-windows", "vcpkg-cmake"), ("x64-windows-static", "libvpx")):
        d = tmp_path / triplet / "share" / port
        d.mkdir(parents=True)
        (d / "copyright").write_text(f"{port} license")
    comps = cl.vcpkg_components(str(tmp_path), ["*"])
    assert [c.name for c in comps] == ["ffmpeg", "libvpx"]
    assert comps[0].texts == [("copyright", "ffmpeg license")]


def test_notices_appendix_for_components_without_text():
    with_text = cl.Component("x", "1", "MIT", "", texts=[("LICENSE-MIT", "MIT TEXT")])
    without = cl.Component("y", "2", "MIT OR Apache-2.0", "", authors=["Jane"])
    out = cl.render_notices("T", [with_text, without], {"BSD-3-Clause": "BSD TEXT"})
    assert "Authors: Jane" in out
    assert "Appendix: standard MIT license text" in out
    assert "Appendix: standard BSD-3-Clause license text" in out
