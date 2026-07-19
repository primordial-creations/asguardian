package main

import (
	"net/http"
	"os/exec"
)

func handler(w http.ResponseWriter, r *http.Request) {
	cmd := exec.Command("ls", "-la")
	cmd.Run()
}
