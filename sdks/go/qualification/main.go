package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	asgard "github.com/primordial-creations/asguardian/sdks/go"
	"os"
	"path/filepath"
	"strings"
)

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func check(value bool) {
	if !value {
		panic("unexpected scan result")
	}
}
func main() {
	root, err := os.MkdirTemp("", "scan fixtures ")
	must(err)
	defer os.RemoveAll(root)
	root, err = filepath.EvalSymlinks(root)
	must(err)
	target := filepath.Join(root, "source with spaces")
	must(os.Mkdir(target, 0700))
	source := filepath.Join(target, "sample.py")
	must(os.WriteFile(source, []byte("value = 1\n"), 0600))
	command := []string{os.Args[1], "-I", "-m", "Asgard.sdk_protocol"}
	version := os.Args[2]
	c, err := asgard.New(command, asgard.Options{EngineVersion: version})
	must(err)
	defer c.Close()
	ctx := context.Background()
	hello, err := c.Handshake(ctx)
	must(err)
	check(hello["engine_version"] == version)
	scan := func(r asgard.Request) asgard.Response { result, err := c.Scan(ctx, r); must(err); return result }
	request := asgard.Request{AuthorizedRoot: root, Target: target, CorrelationID: "clean"}
	clean := scan(request)
	check(clean["complete"] == true && len(clean["findings"].([]any)) == 0 && clean["correlation_id"] == "clean")
	observations := map[string]any{"clean": clean["state"]}
	must(os.WriteFile(source, []byte(strings.Repeat("value = 1\n", 301)), 0600))
	finding := scan(request)
	check(finding["complete"] == true && len(finding["findings"].([]any)) == 1)
	detail := finding["findings"].([]any)[0].(map[string]any)
	check(detail["relative_path"] == "sample.py" && detail["lines_over"] == json.Number("1"))
	observations["finding"] = detail["lines_over"]
	must(os.WriteFile(filepath.Join(target, "second.py"), []byte(strings.Repeat("value = 1\n", 302)), 0600))
	limit := 1
	request.MaxFindings = &limit
	capped := scan(request)
	check(capped["complete"] == false && capped["truncated"] == true && len(capped["findings"].([]any)) == 1)
	check(capped["summary"].(map[string]any)["files_exceeding_threshold"] == json.Number("2"))
	observations["truncated"] = capped["state"]
	for _, invalid := range []string{filepath.Join(root, "missing"), filepath.Dir(root)} {
		_, err := c.Scan(ctx, asgard.Request{AuthorizedRoot: root, Target: invalid})
		var sdk *asgard.Error
		check(errors.As(err, &sdk) && sdk.Code == "engine_error")
		check(sdk.Response["errors"].([]any)[0].(map[string]any)["code"] == "invalid_request")
	}
	observations["invalid_target"] = "invalid_request"
	zero := 0
	_, zeroErr := c.Scan(ctx, asgard.Request{AuthorizedRoot: root, Target: target, MaxFindings: &zero})
	var zeroSDK *asgard.Error
	check(errors.As(zeroErr, &zeroSDK) && zeroSDK.Code == "engine_error")
	observations["zero_limit"] = zeroSDK.Response["errors"].([]any)[0].(map[string]any)["code"]
	linked := filepath.Join(root, "linked")
	must(os.Mkdir(linked, 0700))
	must(os.Symlink(source, filepath.Join(linked, "escape.py")))
	partial := scan(asgard.Request{AuthorizedRoot: linked, Target: linked})
	check(partial["complete"] == false && len(partial["findings"].([]any)) == 0)
	check(partial["errors"].([]any)[0].(map[string]any)["code"] == "scan_io_failure")
	observations["symlink"] = partial["state"]
	wrong, err := asgard.New(command, asgard.Options{EngineVersion: version + "-wrong"})
	must(err)
	defer wrong.Close()
	_, err = wrong.Handshake(ctx)
	var sdk *asgard.Error
	check(errors.As(err, &sdk) && sdk.Code == "engine_version_mismatch")
	observations["mismatch"] = sdk.Code
	closed, err := asgard.New(command, asgard.Options{EngineVersion: version})
	must(err)
	must(closed.Close())
	cancelled, cancel := context.WithCancel(ctx)
	cancel()
	_, err = closed.Handshake(cancelled)
	var closedSDK *asgard.Error
	check(errors.As(err, &closedSDK))
	observations["closed_cancel"] = closedSDK.Code
	fixture, err := filepath.Abs("pipe_fixture.py")
	must(err)
	pipes, err := asgard.New([]string{os.Args[1], "-I", fixture, version}, asgard.Options{EngineVersion: version})
	must(err)
	drained, err := pipes.Handshake(ctx)
	must(err)
	must(pipes.Close())
	observations["pipe_drain"] = drained["state"]
	hotroot := filepath.Join(root, "hotspot scope")
	must(os.Mkdir(hotroot, 0700))
	config := filepath.Join(hotroot, ".heimdall.yml")
	must(os.WriteFile(config, []byte("test_context_enabled: false\n"), 0600))
	must(os.WriteFile(filepath.Join(hotroot, "main.py"), []byte("import hashlib\nhashlib.md5(b'x')\n"), 0600))
	hotrequest := asgard.Request{AuthorizedRoot: hotroot, Target: hotroot, Profile: "security.hotspots"}
	saved, err := os.ReadFile(filepath.Join(hotroot, "main.py"))
	must(err)
	must(os.WriteFile(filepath.Join(hotroot, "main.py"), []byte("value = 1\n"), 0600))
	cleanhot := scan(hotrequest)
	check(cleanhot["complete"] == true && len(cleanhot["findings"].([]any)) == 0)
	observations["hotspot_clean"] = cleanhot["state"]
	must(os.WriteFile(filepath.Join(hotroot, "main.py"), saved, 0600))
	hot := scan(hotrequest)
	check(hot["complete"] == true && len(hot["findings"].([]any)) == 1)
	item := hot["findings"].([]any)[0].(map[string]any)
	observations["hotspot"] = map[string]any{"kind": hot["finding_kind"], "category": item["category"], "priority": item["review_priority"], "review_status": item["review_status"]}
	must(os.WriteFile(filepath.Join(hotroot, "broken.py"), []byte("def broken(:\n"), 0600))
	hotpartial := scan(hotrequest)
	check(hotpartial["complete"] == false && len(hotpartial["findings"].([]any)) == 1)
	check(hotpartial["errors"].([]any)[0].(map[string]any)["stage"] == "parse")
	observations["hotspot_parse"] = hotpartial["state"]
	must(os.WriteFile(filepath.Join(hotroot, "broken.py"), []byte{255}, 0600))
	hotread := scan(hotrequest)
	check(hotread["complete"] == false && len(hotread["findings"].([]any)) == 1)
	check(hotread["errors"].([]any)[0].(map[string]any)["error_type"] == "UnicodeDecodeError")
	observations["hotspot_read"] = hotread["state"]
	must(os.WriteFile(config, []byte("test_context_enabled: []\n"), 0600))
	hotinvalid := scan(hotrequest)
	check(hotinvalid["complete"] == false)
	observations["hotspot_config"] = hotinvalid["errors"].([]any)[0].(map[string]any)["code"]
	result, err := json.Marshal(observations)
	must(err)
	fmt.Println(string(result))
}
