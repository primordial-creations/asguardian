// Package asgard provides a lightweight owner client for the Asgard process protocol.
package asgard

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

type Error struct {
	Code     string
	Response map[string]any
}

func (e *Error) Error() string { return e.Code }
func (e *Error) Unwrap() error {
	switch e.Code {
	case "cancelled":
		return context.Canceled
	case "timeout":
		return context.DeadlineExceeded
	default:
		return nil
	}
}
func fail(code string) error { return &Error{Code: code} }

type Options struct {
	EngineVersion  string
	Timeout        time.Duration
	MaxOutputBytes int
}
type Request struct {
	AuthorizedRoot string
	Target         string
	Profile        string
	MaxFindings    *int
	CorrelationID  string
}

// Response retains owner fields. Completeness must be checked independently of findings.
type Response map[string]any

type Client struct {
	command []string
	options Options
	mu      sync.Mutex
	closed  bool
	active  map[*exec.Cmd]context.CancelCauseFunc
	wait    sync.WaitGroup
}

func New(command []string, options Options) (*Client, error) {
	if len(command) == 0 || !filepath.IsAbs(command[0]) || options.EngineVersion == "" {
		return nil, fail("invalid_configuration")
	}
	for _, arg := range command {
		if arg == "" || strings.ContainsRune(arg, 0) {
			return nil, fail("invalid_configuration")
		}
	}
	if options.Timeout == 0 {
		options.Timeout = 120 * time.Second
	}
	if options.MaxOutputBytes == 0 {
		options.MaxOutputBytes = 20 * 1024 * 1024
	}
	if options.Timeout < 0 || options.MaxOutputBytes < 1024 {
		return nil, fail("invalid_configuration")
	}
	if err := configure(exec.Command(command[0])); err != nil {
		return nil, err
	}
	return &Client{command: append([]string(nil), command...), options: options, active: make(map[*exec.Cmd]context.CancelCauseFunc)}, nil
}
func (c *Client) Close() error {
	c.mu.Lock()
	c.closed = true
	for _, cancel := range c.active {
		cancel(fail("closed"))
	}
	c.mu.Unlock()
	c.wait.Wait()
	return nil
}
func correlation() (string, error) {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "", fail("entropy_unavailable")
	}
	return hex.EncodeToString(b), nil
}
func (c *Client) Handshake(ctx context.Context) (Response, error) {
	ctx, cancel := context.WithTimeout(ctx, c.options.Timeout)
	defer cancel()
	id, err := correlation()
	if err != nil {
		return nil, err
	}
	return c.invoke(ctx, map[string]any{"protocol_version": 1, "operation": "handshake", "correlation_id": id})
}
func (c *Client) Scan(ctx context.Context, request Request) (Response, error) {
	ctx, cancel := context.WithTimeout(ctx, c.options.Timeout)
	defer cancel()
	if request.CorrelationID == "" {
		var err error
		request.CorrelationID, err = correlation()
		if err != nil {
			return nil, err
		}
	}
	if len([]rune(request.CorrelationID)) > 256 {
		return nil, fail("invalid_request")
	}
	if request.Profile == "" {
		request.Profile = "quality.file-length"
	}
	maxFindings := 1000
	if request.MaxFindings != nil {
		maxFindings = *request.MaxFindings
	}
	hello, err := c.invoke(ctx, map[string]any{"protocol_version": 1, "operation": "handshake", "correlation_id": request.CorrelationID})
	if err != nil {
		return nil, err
	}
	supported := false
	for _, profile := range hello["capabilities"].(map[string]any)["profiles"].([]any) {
		if profile == request.Profile {
			supported = true
		}
	}
	if !supported {
		return nil, fail("unsupported_operation")
	}
	return c.invoke(ctx, map[string]any{"protocol_version": 1, "operation": "scan", "correlation_id": request.CorrelationID, "profile": request.Profile, "authorized_root": request.AuthorizedRoot, "target": request.Target, "max_findings": maxFindings})
}

type bounded struct {
	data   bytes.Buffer
	total  int
	limit  int
	retain bool
	cancel context.CancelCauseFunc
}

func (b *bounded) Write(p []byte) (int, error) {
	if len(p) > b.limit-b.total {
		b.cancel(fail("output_limit"))
		return 0, fail("output_limit")
	}
	b.total += len(p)
	if b.retain {
		return b.data.Write(p)
	}
	return len(p), nil
}
func contextError(ctx context.Context) error {
	cause := context.Cause(ctx)
	if cause == nil {
		return nil
	}
	var owned *Error
	if errors.As(cause, &owned) {
		return owned
	}
	if errors.Is(cause, context.DeadlineExceeded) {
		return fail("timeout")
	}
	return fail("cancelled")
}
func (c *Client) invoke(parent context.Context, request map[string]any) (Response, error) {
	raw, err := json.Marshal(request)
	if err != nil {
		return nil, fail("invalid_request")
	}
	if len(raw) > 65536 {
		return nil, fail("request_too_large")
	}
	ctx, cancel := context.WithCancelCause(parent)
	defer cancel(nil)
	cmd := exec.Command(c.command[0], c.command[1:]...)
	if err = configure(cmd); err != nil {
		return nil, err
	}
	stdout := &bounded{limit: c.options.MaxOutputBytes, retain: true, cancel: cancel}
	stderr := &bounded{limit: c.options.MaxOutputBytes, cancel: cancel}
	cmd.Stdin = bytes.NewReader(raw)
	cmd.Stdout = stdout
	cmd.Stderr = stderr
	c.mu.Lock()
	if c.closed {
		c.mu.Unlock()
		return nil, fail("closed")
	}
	if err = contextError(ctx); err != nil {
		c.mu.Unlock()
		return nil, err
	}
	c.active[cmd] = cancel
	c.wait.Add(1)
	c.mu.Unlock()
	defer func() { c.mu.Lock(); delete(c.active, cmd); c.mu.Unlock(); c.wait.Done() }()
	if err = cmd.Start(); err != nil {
		if cause := contextError(ctx); cause != nil {
			return nil, cause
		}
		return nil, fail("engine_unavailable")
	}
	done, watched := make(chan struct{}), make(chan struct{})
	go func() {
		defer close(watched)
		select {
		case <-ctx.Done():
			_ = killGroup(cmd)
		case <-done:
		}
	}()
	err = cmd.Wait()
	close(done)
	<-watched
	cleanup := killGroup(cmd)
	if cause := contextError(ctx); cause != nil {
		return nil, cause
	}
	if cleanup != nil {
		return nil, fail("process_cleanup_failed")
	}
	var exit *exec.ExitError
	if err != nil && !errors.As(err, &exit) {
		return nil, fail("transport_error")
	}
	return c.decode(stdout.data.Bytes(), cmd.ProcessState.ExitCode(), request)
}
func (c *Client) decode(raw []byte, code int, request map[string]any) (Response, error) {
	if !utf8.Valid(raw) {
		return nil, fail("malformed_response")
	}
	var r map[string]any
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(&r); err != nil || r == nil {
		return nil, fail("malformed_response")
	}
	var extra any
	if decoder.Decode(&extra) != io.EOF {
		return nil, fail("malformed_response")
	}
	if r["protocol_version"] != json.Number("1") {
		return nil, fail("version_mismatch")
	}
	if r["engine_version"] != c.options.EngineVersion {
		return nil, fail("engine_version_mismatch")
	}
	complete, ok1 := r["complete"].(bool)
	truncated, ok2 := r["truncated"].(bool)
	findings, ok3 := r["findings"].([]any)
	errs, ok4 := r["errors"].([]any)
	id, ok5 := r["scan_id"].(string)
	if !ok1 || !ok2 || !ok3 || !ok4 || !ok5 || id == "" || r["correlation_id"] != request["correlation_id"] {
		return nil, fail("malformed_response")
	}
	for _, items := range [][]any{findings, errs} {
		for _, item := range items {
			if _, ok := item.(map[string]any); !ok {
				return nil, fail("malformed_response")
			}
		}
	}
	if r["state"] == "error" && code == 2 && !complete && len(errs) > 0 {
		return nil, &Error{Code: "engine_error", Response: r}
	}
	valid := false
	if request["operation"] == "handshake" {
		caps, ok := r["capabilities"].(map[string]any)
		if ok {
			_, profiles := caps["profiles"].([]any)
			valid = profiles && caps["transport"] == "single-request-stdio" && r["state"] == "ready" && code == 0 && complete && !truncated && len(findings) == 0 && len(errs) == 0
		}
	} else {
		expected := 0
		if len(findings) > 0 {
			expected = 1
		}
		valid = (r["state"] == "complete" && complete && !truncated && len(errs) == 0 && code == expected) || (r["state"] == "incomplete" && !complete && code == 1 && (truncated || len(errs) > 0))
	}
	if !valid {
		return nil, fail("malformed_response")
	}
	return Response(r), nil
}
