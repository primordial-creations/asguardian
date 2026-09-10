package asgard_test

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	asgard "github.com/primordial-creations/asguardian/sdks/go"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
)

func TestHelper(t *testing.T) {
	if len(os.Args) < 2 || os.Args[len(os.Args)-2] != "asgard-fixture" {
		return
	}
	mode := os.Args[len(os.Args)-1]
	if strings.HasPrefix(mode, "child=") {
		binary, _ := os.Executable()
		cmd := exec.Command(binary, "-test.run=TestHelper", "--", "asgard-fixture", "sleep")
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Start(); err != nil {
			os.Exit(3)
		}
		marker := strings.TrimPrefix(mode, "child=")
		if err := os.WriteFile(marker+".pending", []byte(strconv.Itoa(cmd.Process.Pid)), 0600); err != nil {
			panic(err)
		}
		if err := os.Rename(marker+".pending", marker); err != nil {
			panic(err)
		}
		time.Sleep(time.Minute)
		os.Exit(0)
	}
	var req map[string]any
	json.NewDecoder(os.Stdin).Decode(&req)
	if mode == "sleep" {
		time.Sleep(time.Minute)
		os.Exit(0)
	}
	if mode == "stdout" || mode == "stderr" {
		out := os.Stdout
		if mode == "stderr" {
			out = os.Stderr
		}
		out.Write(make([]byte, 100000))
		time.Sleep(time.Minute)
		os.Exit(0)
	}
	if mode == "malformed" {
		fmt.Print("null")
		os.Exit(0)
	}
	r := map[string]any{"protocol_version": 1, "engine_version": "fixture", "scan_id": "id", "correlation_id": req["correlation_id"], "state": "ready", "complete": true, "truncated": false, "findings": []any{}, "errors": []any{}, "capabilities": map[string]any{"profiles": []string{"quality.file-length"}, "transport": "single-request-stdio"}}
	code := 0
	if req["operation"] == "scan" {
		r["state"] = "complete"
		switch mode {
		case "finding":
			r["findings"] = []any{map[string]any{"relative_path": "sample.py"}}
			code = 1
		case "incomplete":
			r["state"] = "incomplete"
			r["complete"] = false
			r["truncated"] = true
			code = 1
		case "lying":
			r["errors"] = []any{map[string]any{"code": "missing_tool"}}
		case "error":
			r["state"] = "error"
			r["complete"] = false
			r["errors"] = []any{map[string]any{"code": "invalid_request"}}
			code = 2
		}
	}
	if mode == "version" {
		r["engine_version"] = "other"
	}
	json.NewEncoder(os.Stdout).Encode(r)
	os.Exit(code)
}
func client(t *testing.T, mode string, timeout time.Duration) *asgard.Client {
	t.Helper()
	binary, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	c, err := asgard.New([]string{binary, "-test.run=TestHelper", "--", "asgard-fixture", mode}, asgard.Options{EngineVersion: "fixture", Timeout: timeout, MaxOutputBytes: 1024})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { c.Close() })
	return c
}
func scan(c *asgard.Client, ctx context.Context) (asgard.Response, error) {
	return c.Scan(ctx, asgard.Request{AuthorizedRoot: "/fixture", Target: "/fixture/source"})
}
func requireCode(t *testing.T, err error, code string) {
	t.Helper()
	var sdk *asgard.Error
	if !errors.As(err, &sdk) || sdk.Code != code {
		t.Fatalf("want %s got %v", code, err)
	}
}
func TestTruth(t *testing.T) {
	for _, mode := range []string{"clean", "finding", "incomplete"} {
		t.Run(mode, func(t *testing.T) {
			c := client(t, mode, 10*time.Second)
			r, err := scan(c, context.Background())
			if err != nil {
				t.Fatal(err)
			}
			if r["complete"] != (mode != "incomplete") {
				t.Fatal(r)
			}
			if (len(r["findings"].([]any)) > 0) != (mode == "finding") {
				t.Fatal(r)
			}
		})
	}
}
func TestErrors(t *testing.T) {
	for mode, code := range map[string]string{"malformed": "malformed_response", "lying": "malformed_response", "version": "engine_version_mismatch", "error": "engine_error"} {
		t.Run(mode, func(t *testing.T) {
			_, err := scan(client(t, mode, 10*time.Second), context.Background())
			requireCode(t, err, code)
		})
	}
}
func TestBounds(t *testing.T) {
	for _, mode := range []string{"sleep", "stdout", "stderr"} {
		t.Run(mode, func(t *testing.T) {
			_, err := scan(client(t, mode, 300*time.Millisecond), context.Background())
			code := "output_limit"
			if mode == "sleep" {
				code = "timeout"
			}
			requireCode(t, err, code)
		})
	}
}
func TestCancellationAndClose(t *testing.T) {
	for _, closeClient := range []bool{false, true} {
		t.Run(strconv.FormatBool(closeClient), func(t *testing.T) {
			c := client(t, "sleep", 10*time.Second)
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			done := make(chan error, 1)
			go func() { _, err := scan(c, ctx); done <- err }()
			time.Sleep(100 * time.Millisecond)
			if closeClient {
				c.Close()
			} else {
				cancel()
			}
			select {
			case err := <-done:
				code := "cancelled"
				if closeClient {
					code = "closed"
				}
				requireCode(t, err, code)
			case <-time.After(3 * time.Second):
				t.Fatal("did not drain")
			}
			c.Close()
			_, err := scan(c, context.Background())
			requireCode(t, err, "closed")
		})
	}
}
func TestIndependentAndUnsupported(t *testing.T) {
	first := client(t, "clean", 10*time.Second)
	second := client(t, "clean", 10*time.Second)
	first.Close()
	if _, err := scan(second, context.Background()); err != nil {
		t.Fatal(err)
	}
	_, err := second.Scan(context.Background(), asgard.Request{Profile: "other"})
	requireCode(t, err, "unsupported_operation")
	missing, err := asgard.New([]string{"/nonexistent/asgard"}, asgard.Options{EngineVersion: "1"})
	if err != nil {
		t.Fatal(err)
	}
	defer missing.Close()
	_, err = missing.Handshake(context.Background())
	requireCode(t, err, "engine_unavailable")
}

func TestChildCleanup(t *testing.T) {
	marker := filepath.Join(t.TempDir(), "child.pid")
	c := client(t, "child="+marker, 500*time.Millisecond)
	_, err := c.Handshake(context.Background())
	requireCode(t, err, "timeout")
	pid, err := os.ReadFile(marker)
	if err != nil {
		t.Fatal(err)
	}
	number, err := strconv.Atoi(string(pid))
	if err != nil || number <= 0 {
		t.Fatal("invalid child PID")
	}
	deadline := time.Now().Add(2 * time.Second)
	for {
		stat, err := os.ReadFile("/proc/" + string(pid) + "/stat")
		if errors.Is(err, os.ErrNotExist) || errors.Is(err, syscall.ESRCH) {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		if strings.Fields(string(stat))[2] == "Z" {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("descendant survived group cleanup")
		}
		time.Sleep(10 * time.Millisecond)
	}
}
