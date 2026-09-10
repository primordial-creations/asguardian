//go:build !linux && !darwin

package asgard

import (
	"errors"
	"os/exec"
)

func configure(cmd *exec.Cmd) error {
	return errors.New("process groups currently supported on Linux/Darwin only")
}
func killGroup(cmd *exec.Cmd) error { return cmd.Process.Kill() }
