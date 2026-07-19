// FP: a genuinely parameterized query (constant SQL literal with a `?`
// placeholder, tainted value bound as a driver parameter, not
// string-concatenated into the query) is safe and must not flag
// (adversarial review MAJOR-2). Idiomatic, correct Go DB code.
package main

import (
	"database/sql"
	"net/http"
)

func handler(w http.ResponseWriter, r *http.Request, db *sql.DB) {
	name := r.URL.Query().Get("name")
	rows, _ := db.Query("SELECT * FROM users WHERE name = ?", name)
	_ = rows
}
