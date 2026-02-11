.PHONY: run

run:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-NoExit','-Command','python -u server.py'; Start-Sleep -Seconds 1; Start-Process powershell -ArgumentList '-NoExit','-Command','python -u main.py'; Start-Sleep -Seconds 1; Start-Process powershell -ArgumentList '-NoExit','-Command','python -u main.py'"
