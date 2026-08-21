#!/usr/bin/env python3
# test_analyze.py — clean-computer 引擎单元测试（纯标准库，零依赖）
# 运行: python3 -m unittest tests/test_analyze.py -v
# 或通过 tests/run_all.sh 统一执行。
#
# 覆盖：analyze.py 全部核心函数 + report.py HTML 生成 + JSON Schema 校验。
# fixtures 全部动态构造于临时目录，不污染真实环境。

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import analyze as A  # noqa: E402


def make_fixture():
    """构造：重复文件(2处)、僵尸文件(400天前atime)、新鲜文件、大文件。返回根目录。"""
    root = tempfile.mkdtemp(prefix="cc-test-")
    os.makedirs(os.path.join(root, "cache_a"), exist_ok=True)
    os.makedirs(os.path.join(root, "cache_b"), exist_ok=True)
    os.makedirs(os.path.join(root, "big"), exist_ok=True)
    dup = "D" * 1500
    with open(os.path.join(root, "cache_a", "dup1.txt"), "w") as f:
        f.write(dup)
    with open(os.path.join(root, "cache_b", "dup1_copy.txt"), "w") as f:
        f.write(dup)
    zombie = os.path.join(root, "cache_a", "zombie.log")
    with open(zombie, "w") as f:
        f.write("Z" * 200000)
    with open(os.path.join(root, "cache_a", "fresh.log"), "w") as f:
        f.write("F" * 200000)
    past = time.time() - 400 * 86400
    os.utime(zombie, (past, time.time()))
    with open(os.path.join(root, "big", "bigfile.bin"), "wb") as f:
        f.write(b"\0" * (600 * 1024 * 1024))
    return root


class TestDirStats(unittest.TestCase):
    def test_stats_and_zombie(self):
        root = make_fixture()
        try:
            s = A.dir_stats(os.path.join(root, "cache_a"), zombie_days=180)
            self.assertEqual(s["file_count"], 3)
            self.assertEqual(s["size_bytes"], 401500)
            self.assertEqual(s["zombie_bytes"], 200000)
            self.assertEqual(s["last_access_days"], 0)  # fresh.log 刚访问
            self.assertTrue(s["top_subdirs"])  # Top 子目录非空
        finally:
            import shutil
            shutil.rmtree(root)

    def test_missing_dir(self):
        s = A.dir_stats("/nonexistent/path/xyz", zombie_days=180)
        self.assertEqual(s["size_bytes"], 0)
        self.assertEqual(s["file_count"], 0)


class TestDuplicates(unittest.TestCase):
    def test_sampling_hash_consistency(self):
        root = make_fixture()
        try:
            h1 = A.sample_hash(os.path.join(root, "cache_a", "dup1.txt"))
            h2 = A.sample_hash(os.path.join(root, "cache_b", "dup1_copy.txt"))
            self.assertEqual(h1, h2)
        finally:
            import shutil
            shutil.rmtree(root)

    def test_find_duplicates(self):
        root = make_fixture()
        try:
            dups = A.find_duplicates(
                [os.path.join(root, "cache_a"), os.path.join(root, "cache_b")],
                min_group=2, limit=50)
            self.assertEqual(len(dups), 1)
            self.assertEqual(dups[0]["count"], 2)
            self.assertEqual(dups[0]["size_bytes"], 1500)
        finally:
            import shutil
            shutil.rmtree(root)


class TestLargeFiles(unittest.TestCase):
    def test_scan_large(self):
        root = make_fixture()
        try:
            big = A.scan_large_files([os.path.join(root, "big")],
                                     min_bytes=500 * 1024 * 1024, limit=10)
            self.assertGreaterEqual(len(big), 1)
            self.assertEqual(big[0]["size_bytes"], 600 * 1024 * 1024)
        finally:
            import shutil
            shutil.rmtree(root)


class TestPredict(unittest.TestCase):
    def test_predict_logic(self):
        cats = [
            {"id": "trash", "label": "废纸篓", "path": "x", "exists": True,
             "size_bytes": 1000, "reclaimable_bytes": 0, "risk": "yellow"},
            {"id": "caches", "label": "应用缓存", "path": "y", "exists": True,
             "size_bytes": 1000, "reclaimable_bytes": 500, "risk": "green"},
        ]
        pred = A.predict(cats, [{"size_bytes": 1500, "count": 2, "files": ["a", "b"]}], [])
        trash = [c for c in pred["categories"] if c["id"] == "trash"][0]
        self.assertEqual(trash["reclaimable_bytes"], 1000)  # 回收站全释放
        self.assertEqual(pred["reclaimable_total_bytes"], 1500)
        self.assertEqual(pred["dup_reclaimable_bytes"], 1500)


class TestSnapshotCompare(unittest.TestCase):
    def test_snapshot_roundtrip(self):
        osf = "macos"
        report = {
            "schema_version": A.SCHEMA_VERSION, "os": osf,
            "generated_at": "2026-01-01T00:00:00+0800",
            "zombie_days_threshold": 180,
            "categories": [{"id": "caches", "label": "应用缓存", "path": "/x",
                            "size_bytes": 1000, "file_count": 2, "zombie_bytes": 0,
                            "last_access_days": 0, "exists": True, "risk": "green",
                            "top_subdirs": []}],
            "large_files": [], "duplicates": [], "prediction": None,
        }
        with tempfile.TemporaryDirectory() as td:
            old_dir = A.SNAPSHOT_DIR
            A.SNAPSHOT_DIR = td
            try:
                path = A.save_snapshot(report, tag="test")
                self.assertTrue(os.path.exists(path))
                loaded = A.load_snapshot(osf, tag="test")
                self.assertIsNotNone(loaded)
                self.assertEqual(loaded["categories"][0]["size_bytes"], 1000)
            finally:
                A.SNAPSHOT_DIR = old_dir

    def test_compare_reports(self):
        base = {"generated_at": "b", "os": "macos", "categories": [
            {"id": "caches", "label": "应用缓存", "risk": "green",
             "size_bytes": 1500}]}
        now = {"generated_at": "n", "os": "macos", "categories": [
            {"id": "caches", "label": "应用缓存", "risk": "green",
             "size_bytes": 500}]}
        comp = A.compare_reports(base, now)
        self.assertEqual(comp["released_bytes"], 1000)
        self.assertEqual(comp["categories"][0]["delta_bytes"], -1000)


class TestWindowsMapping(unittest.TestCase):
    def test_category_map_windows(self):
        cats = A.category_map("windows")
        ids = [c["id"] for c in cats]
        self.assertIn("temp_user", ids)
        self.assertIn("temp_sys", ids)
        self.assertIn("edge", ids)
        self.assertIn("chrome", ids)
        self.assertIn("wechat", ids)
        self.assertIn("winupdate", ids)
        self.assertIn("trash", ids)
        # 路径用环境变量拼接，非空且为绝对路径形式
        for c in cats:
            self.assertTrue(c["path"], f"{c['id']} 路径为空")
            self.assertIn(c["risk"], ("green", "yellow"))
        # Windows 品类不引入 Linux/macOS 专属字段
        for c in cats:
            self.assertNotEqual(c["id"], "containers")

    def test_win_recycle_stats_fallback(self):
        # 在非 Windows 环境，_win_recycle_stats 应返回零值结构（不抛异常）
        s = A._win_recycle_stats()
        for k in ("size_bytes", "file_count", "zombie_bytes", "reclaimable_bytes"):
            self.assertIn(k, s)


class TestJSONSchema(unittest.TestCase):
    def test_cli_json_schema(self):
        py = sys.executable
        r = subprocess.run(
            [py, os.path.join(SCRIPTS, "analyze.py"), "--mode", "scan", "--json"],
            capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        d = json.loads(r.stdout)
        self.assertEqual(d["schema_version"], "1.0")
        self.assertIn(d["os"], ("macos", "windows"))
        self.assertTrue(d["categories"])
        c0 = d["categories"][0]
        for k in ("id", "label", "path", "size_bytes", "file_count",
                  "zombie_bytes", "reclaimable_bytes", "risk", "exists",
                  "last_access_days", "top_subdirs"):
            self.assertIn(k, c0)


class TestReportHTML(unittest.TestCase):
    def test_report_pipeline(self):
        py = sys.executable
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "report.html")
            p1 = subprocess.run(
                [py, os.path.join(SCRIPTS, "analyze.py"), "--mode", "scan", "--json"],
                capture_output=True, text=True, timeout=180)
            self.assertEqual(p1.returncode, 0)
            p2 = subprocess.run(
                [py, os.path.join(SCRIPTS, "report.py"), "-o", out],
                input=p1.stdout, capture_output=True, text=True, timeout=60)
            self.assertEqual(p2.returncode, 0, p2.stderr[-300:])
            html = open(out, encoding="utf-8").read()
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("磁盘画像", html)
            self.assertIn("</html>", html)

    def test_compare_report_pipeline(self):
        py = sys.executable
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "compare.html")
            base = {"generated_at": "b", "os": "macos", "categories": [
                {"id": "caches", "label": "应用缓存", "risk": "green",
                 "size_bytes": 1500}]}
            now = {"generated_at": "n", "os": "macos", "categories": [
                {"id": "caches", "label": "应用缓存", "risk": "green",
                 "size_bytes": 500}]}
            comp = A.compare_reports(base, now)
            p = subprocess.run(
                [py, os.path.join(SCRIPTS, "report.py"), "-o", out],
                input=json.dumps(comp), capture_output=True, text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr[-300:])
            html = open(out, encoding="utf-8").read()
            self.assertIn("释放 1000 B", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
