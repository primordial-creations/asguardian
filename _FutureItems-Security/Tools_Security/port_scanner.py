#!/usr/bin/env python3
"""
Port Scanner
Scans for open ports on target hosts for security assessment.
"""

import socket
import argparse
import concurrent.futures
from typing import Dict, List, Tuple
from datetime import datetime


class PortScanner:
    """Network port scanner for security assessments."""

    # Common service ports
    COMMON_PORTS = {
        20: 'FTP Data',
        21: 'FTP Control',
        22: 'SSH',
        23: 'Telnet',
        25: 'SMTP',
        53: 'DNS',
        80: 'HTTP',
        110: 'POP3',
        111: 'RPC',
        135: 'MSRPC',
        139: 'NetBIOS',
        143: 'IMAP',
        443: 'HTTPS',
        445: 'SMB',
        993: 'IMAPS',
        995: 'POP3S',
        1433: 'MSSQL',
        1521: 'Oracle',
        3306: 'MySQL',
        3389: 'RDP',
        5432: 'PostgreSQL',
        5900: 'VNC',
        6379: 'Redis',
        8080: 'HTTP Proxy',
        8443: 'HTTPS Alt',
        27017: 'MongoDB'
    }

    # Security risk assessment
    HIGH_RISK_PORTS = {23, 21, 135, 139, 445, 3389, 5900}
    MEDIUM_RISK_PORTS = {25, 110, 143, 111}

    def __init__(self, timeout: float = 1.0):
        self.timeout = timeout
        self.results: Dict[int, Dict] = {}

    def scan_port(self, host: str, port: int) -> Tuple[int, bool, str]:
        """Scan a single port."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                service = self.COMMON_PORTS.get(port, 'Unknown')
                return port, True, service
            return port, False, ''
        except socket.error:
            return port, False, ''

    def get_banner(self, host: str, port: int) -> str:
        """Try to grab service banner."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((host, port))
            sock.send(b'HEAD / HTTP/1.0\r\n\r\n')
            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            sock.close()
            return banner[:100] if banner else ''
        except (socket.error, socket.timeout):
            return ''

    def scan_host(self, host: str, ports: List[int], workers: int = 100) -> Dict:
        """Scan multiple ports on a host."""
        open_ports = []
        scan_start = datetime.now()

        # Resolve hostname
        try:
            ip_address = socket.gethostbyname(host)
        except socket.gaierror:
            return {'error': f'Cannot resolve hostname: {host}'}

        print(f"Scanning {host} ({ip_address})...")
        print(f"Ports to scan: {len(ports)}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_port = {
                executor.submit(self.scan_port, ip_address, port): port
                for port in ports
            }

            for future in concurrent.futures.as_completed(future_to_port):
                port, is_open, service = future.result()
                if is_open:
                    open_ports.append({
                        'port': port,
                        'service': service,
                        'risk': self.assess_risk(port)
                    })

        scan_end = datetime.now()
        duration = (scan_end - scan_start).total_seconds()

        # Sort by port number
        open_ports.sort(key=lambda x: x['port'])

        self.results = {
            'host': host,
            'ip': ip_address,
            'scan_time': scan_start.isoformat(),
            'duration': f'{duration:.2f}s',
            'ports_scanned': len(ports),
            'open_ports': open_ports,
            'summary': self.generate_summary(open_ports)
        }

        return self.results

    def assess_risk(self, port: int) -> str:
        """Assess security risk of an open port."""
        if port in self.HIGH_RISK_PORTS:
            return 'HIGH'
        elif port in self.MEDIUM_RISK_PORTS:
            return 'MEDIUM'
        return 'LOW'

    def generate_summary(self, open_ports: List[Dict]) -> Dict:
        """Generate security summary."""
        summary = {
            'total_open': len(open_ports),
            'high_risk': 0,
            'medium_risk': 0,
            'low_risk': 0,
            'recommendations': []
        }

        for port_info in open_ports:
            risk = port_info['risk']
            if risk == 'HIGH':
                summary['high_risk'] += 1
            elif risk == 'MEDIUM':
                summary['medium_risk'] += 1
            else:
                summary['low_risk'] += 1

        # Generate recommendations
        port_numbers = [p['port'] for p in open_ports]

        if 23 in port_numbers:
            summary['recommendations'].append("CRITICAL: Telnet (23) is insecure. Use SSH instead.")
        if 21 in port_numbers:
            summary['recommendations'].append("HIGH: FTP (21) transmits credentials in plain text. Use SFTP.")
        if 3389 in port_numbers:
            summary['recommendations'].append("HIGH: RDP (3389) should be restricted or use VPN.")
        if 445 in port_numbers:
            summary['recommendations'].append("HIGH: SMB (445) should not be exposed to internet.")
        if 6379 in port_numbers:
            summary['recommendations'].append("CRITICAL: Redis (6379) often runs without authentication.")
        if 27017 in port_numbers:
            summary['recommendations'].append("HIGH: MongoDB (27017) default config may be insecure.")

        return summary

    def print_report(self):
        """Print scan report."""
        if 'error' in self.results:
            print(f"\nError: {self.results['error']}")
            return 1

        print("\n" + "=" * 70)
        print("PORT SCAN REPORT")
        print("=" * 70)

        print(f"\nTarget: {self.results['host']} ({self.results['ip']})")
        print(f"Scan Time: {self.results['scan_time']}")
        print(f"Duration: {self.results['duration']}")
        print(f"Ports Scanned: {self.results['ports_scanned']}")

        print("\n" + "-" * 40)
        print("OPEN PORTS")
        print("-" * 40)

        if self.results['open_ports']:
            print(f"\n{'Port':<10}{'Service':<20}{'Risk':<10}")
            print("-" * 40)

            for port_info in self.results['open_ports']:
                risk_indicator = {
                    'HIGH': '⚠️ ',
                    'MEDIUM': '⚡ ',
                    'LOW': '✓ '
                }.get(port_info['risk'], '  ')

                print(f"{port_info['port']:<10}{port_info['service']:<20}{risk_indicator}{port_info['risk']}")
        else:
            print("\nNo open ports found.")

        # Summary
        summary = self.results['summary']
        print("\n" + "-" * 40)
        print("SECURITY SUMMARY")
        print("-" * 40)
        print(f"Total Open Ports: {summary['total_open']}")
        print(f"High Risk: {summary['high_risk']}")
        print(f"Medium Risk: {summary['medium_risk']}")
        print(f"Low Risk: {summary['low_risk']}")

        if summary['recommendations']:
            print("\n" + "-" * 40)
            print("RECOMMENDATIONS")
            print("-" * 40)
            for rec in summary['recommendations']:
                print(f"\n• {rec}")

        print("\n" + "=" * 70)

        return 1 if summary['high_risk'] > 0 else 0


def parse_ports(port_spec: str) -> List[int]:
    """Parse port specification (e.g., '80,443,8000-8100')."""
    ports = []

    for part in port_spec.split(','):
        if '-' in part:
            start, end = part.split('-')
            ports.extend(range(int(start), int(end) + 1))
        else:
            ports.append(int(part))

    return sorted(set(ports))


def main():
    parser = argparse.ArgumentParser(
        description='Scan ports on target host for security assessment'
    )
    parser.add_argument(
        'host',
        help='Target host to scan (hostname or IP)'
    )
    parser.add_argument(
        '-p', '--ports',
        default='common',
        help='Ports to scan: "common", "all", or port spec like "80,443,8000-8100"'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=float,
        default=1.0,
        help='Connection timeout in seconds (default: 1.0)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=100,
        help='Number of concurrent workers (default: 100)'
    )
    parser.add_argument(
        '--top',
        type=int,
        help='Scan top N most common ports'
    )

    args = parser.parse_args()
    scanner = PortScanner(timeout=args.timeout)

    # Determine ports to scan
    if args.ports == 'common':
        ports = list(PortScanner.COMMON_PORTS.keys())
    elif args.ports == 'all':
        ports = list(range(1, 65536))
    else:
        try:
            ports = parse_ports(args.ports)
        except ValueError:
            print(f"Error: Invalid port specification: {args.ports}")
            return 1

    if args.top:
        ports = sorted(PortScanner.COMMON_PORTS.keys())[:args.top]

    scanner.scan_host(args.host, ports, workers=args.workers)
    return scanner.print_report()


if __name__ == '__main__':
    exit(main())
