package main

import (
	"database/sql"
	"net/http"
)

func handler(w http.ResponseWriter, r *http.Request) {
	m := make(map[string]string)
	m["a"] = r.URL.Query().Get("name")
	db.Query(m["a"])
}

var db *sql.DB
