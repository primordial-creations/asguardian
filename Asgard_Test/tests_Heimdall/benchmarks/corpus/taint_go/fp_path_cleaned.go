package main

import (
	"net/http"
	"os"
	"path/filepath"
)

func handler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("file")
	safe := filepath.Clean(name)
	os.Open(safe)
}
