package main

import "net/http"

func handler(w http.ResponseWriter, r *http.Request) {
	target := r.URL.Query().Get("url")
	http.Get(target)
}
